"""Admit downloaded larger development candidates on the same pinned Radeon runtime."""
import argparse
from functools import partial
import gzip
import json
from pathlib import Path
import subprocess
from uuid import uuid4

from benchmarks.competitive_slm.admission import GATES, cpu_server, chat_ok, request, test_gpu
from benchmarks.competitive_slm.tc_v2_candidate import (
    read_embedded_template, server_environment, server_template_source, verify_launch, verify_runtime,
)
from benchmarks.root_cause.historical_replay import gpu_server, legacy
from scripts.tools.verify_ij06_evidence import verify_gpu
from .archive import check_text, digest
from .q2_development import REGISTRY
from .runtime import ROOT, canonical, fingerprint, write_json

PINS = Path(__file__).with_name("larger_candidate_pins.json")
ADDITIONAL_PINS = Path(__file__).with_name("additional_candidate_pins.json")


def local_asset(candidate, assets):
    model = assets/".tools/models/AEVE-larger-candidates"/candidate["file"]
    if not model.is_file():
        raise FileNotFoundError(f"verified download unavailable for {candidate['code']}")
    if model.stat().st_size != candidate["size"] or digest(model) != candidate["sha256"]:
        raise ValueError("local GGUF differs from the pinned ModelScope asset")
    return model


def download(candidate, assets, proxy=None):
    folder = assets/".tools/models/AEVE-larger-candidates"
    folder.mkdir(parents=True,exist_ok=True)
    from .controller import gpu_lock
    with gpu_lock(folder,candidate["file"]+".download.lock"):
        return copy_ranges(candidate,assets,folder,proxy)


def copy_ranges(candidate, assets, folder, proxy):
    final = folder/candidate["file"]
    partial = final.with_suffix(final.suffix+".part")
    if final.exists():
        return local_asset(candidate,assets)
    url = f"https://www.modelscope.cn/models/{candidate['repo']}/resolve/{candidate['revision']}/{candidate['file']}"
    flags = ["curl","--silent","--show-error","--fail","--location","--connect-timeout","25",
             "--max-time","120","--limit-rate","16M","--write-out","%{http_code}"]
    if proxy:
        flags += ["--proxy",proxy]
    chunk = partial.with_suffix(".chunk")
    failed = 0
    while not partial.is_file() or partial.stat().st_size < candidate["size"]:
        start = partial.stat().st_size if partial.is_file() else 0
        count = min(128*1024*1024,candidate["size"]-start)
        command = [*flags,"--range",f"{start}-{start+count-1}","--max-filesize",str(count),"--output",str(chunk),url]
        reply = subprocess.run(command,capture_output=True,check=False)
        if reply.returncode or reply.stdout != b"206" or not chunk.is_file() or chunk.stat().st_size != count:
            failed += 1
            if failed >= 3:
                raise OSError(f"verified range failed after three attempts at byte {start}")
            continue
        with partial.open("ab") as target, chunk.open("rb") as source:
            from shutil import copyfileobj
            copyfileobj(source,target,1<<20)
        failed = 0
        print(candidate["code"],start+count,candidate["size"],flush=True)
    chunk.unlink(missing_ok=True)
    if digest(partial) != candidate["sha256"]:
        raise ValueError("download differs from the ModelScope digest")
    partial.rename(final)
    return final


def test(candidate, assets, output, port, *, matched_development=False, pins=PINS):
    # Candidate E supplies the verified engine identity, independently of the larger model.
    engine = assets/".tools/ij07-toolchoice-p4b-vulkan"
    reference = json.loads(REGISTRY.read_bytes())["candidates"]["E"]
    control = verify_runtime("E",assets/reference["asset"],engine)
    model = local_asset(candidate,assets)
    embedded = read_embedded_template(model)
    from hashlib import sha256
    template = sha256(server_template_source(embedded).encode()).hexdigest()
    alias = "ij07-candidate-" + candidate["code"].lower()
    run = "ij073-larger-" + uuid4().hex
    target = output/run
    target.mkdir(parents=True)
    report = {"run_id":run,"evidence_type":"runtime_admission","candidate":candidate,
              "git":legacy.git_state(),"pins_sha256":digest(pins),"engine":control["engine"],
              "template_sha256":template,"gates":dict.fromkeys(GATES,"NOT_RUN"),"wire":[]}
    gates = report["gates"]
    gates["artifact_identity"] = "PASS"
    development = target / "development.jsonl"
    report["matched_development"] = {"coverage": "NOT_RUN"}
    def bind(client):
        return partial(request,client,alias,wire=report["wire"],disable_thinking=True)
    binary = assets/"runtime/llama-cpp/cpu/llama-server.exe"
    with cpu_server(binary,model,port,target/"cpu.log",alias) as (client,build):
        gates["load"] = "PASS"
        gates["cpu_reference"] = "PASS" if chat_ok(bind(client)) else "FAIL"
        report["cpu"] = {"binary_sha256":digest(binary),"build":build}
    with gpu_server(engine/"llama-server.exe",model,"vulkan",server_environment(),target,
                    port,"vulkan",True,alias=alias, mission_id="IJ-0.7.3",
                    lease_owner="aeve-admission", runtime_session=run) as (client,launch):
        expected = {**control,"engine":{**control["engine"],"layers":launch["layers_total"]},
                    "template":{"sha256":template}}
        verify_launch(launch,expected)
        report["gpu"] = launch
        test_gpu(bind(client),report)
        if matched_development and all(gates[k] == "PASS" for k in GATES if k != "gpu_execution"):
            from .larger_development import evaluate_development
            report["matched_development"] = evaluate_development(candidate["code"], client, development)
    launch_file = target/"launch.json"
    write_json(launch_file,{**report["gpu"],"status":"PASS"})
    counter = target/report["gpu"]["counter_file"]
    gates["gpu_execution"] = "PASS" if verify_gpu({"gpu_launch":launch_file,"gpu_counters":counter},"vulkan") else "FAIL"
    public = target/"portable"
    public.mkdir()
    files = [report["gpu"]["counter_file"], report["gpu"]["trace_file"]]
    if development.is_file():
        files.append(development.name)
        if gates["gpu_execution"] != "PASS":
            report["matched_development"]["coverage"] = "BLOCKED"
    for name in files:
        data = (target/name).read_bytes()
        check_text(data)
        (public/(name+".gz")).write_bytes(gzip.compress(data,mtime=0))
    report["status"] = "PASS" if all(value=="PASS" for value in gates.values()) else (
        "FAIL" if "FAIL" in gates.values() else "BLOCKED")
    report["sha256"] = {p.name:digest(p) for p in sorted(public.iterdir())}
    check_text(canonical(report))
    write_json(public/"report.json",report)
    print(candidate["code"],report["status"],fingerprint(report),flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    registries = {row["code"]: (row, pins) for pins in (PINS, ADDITIONAL_PINS)
                  for row in json.loads(pins.read_bytes())["candidates"]}
    parser.add_argument("candidate", choices=tuple(registries))
    parser.add_argument("--assets",type=Path,default=ROOT.parent.parent)
    parser.add_argument("--out",type=Path,default=ROOT/".runtime/larger-judge-admission")
    parser.add_argument("--port",type=int,default=18745)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--verify-asset",action="store_true")
    action.add_argument("--download",action="store_true")
    parser.add_argument("--proxy")
    parser.add_argument("--matched-development", action="store_true")
    args = parser.parse_args()
    pin, registry = registries[args.candidate]
    if args.download:
        download(pin,args.assets.resolve(),args.proxy)
        print(pin["code"],pin["sha256"])
    elif args.verify_asset:
        local_asset(pin,args.assets.resolve())
        print(pin["code"],pin["sha256"])
    else:
        test(pin,args.assets.resolve(),args.out.resolve(),args.port,matched_development=args.matched_development,pins=registry)


if __name__ == "__main__":
    main()
