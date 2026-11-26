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
    final = folder/candidate["file"]
    partial = final.with_suffix(final.suffix+".part")
    if final.exists():
        return local_asset(candidate,assets)
    url = f"https://www.modelscope.cn/models/{candidate['repo']}/resolve/{candidate['revision']}/{candidate['file']}"
    flags = ["curl","--silent","--show-error","--fail","--location","--continue-at","-",
             "--connect-timeout","25","--speed-limit","65536","--speed-time","90",
             "--limit-rate","16M","--max-time","360","--output",str(partial)]
    if proxy:
        flags += ["--proxy",proxy]
    stalled = 0
    while not partial.is_file() or partial.stat().st_size < candidate["size"]:
        previous = partial.stat().st_size if partial.is_file() else 0
        subprocess.run([*flags,url],check=False)
        current = partial.stat().st_size if partial.is_file() else 0
        if current < previous or current > candidate["size"]:
            raise ValueError("download resume size changed unexpectedly")
        stalled = 0 if current > previous else stalled+1
        print(candidate["code"],current,candidate["size"],flush=True)
        if stalled >= 3:
            raise OSError("download failed to make progress in three consecutive attempts")
    if digest(partial) != candidate["sha256"]:
        raise ValueError("download differs from the ModelScope digest")
    partial.rename(final)
    return final


def test(candidate, assets, output, port):
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
              "git":legacy.git_state(),"pins_sha256":digest(PINS),"engine":control["engine"],
              "template_sha256":template,"gates":dict.fromkeys(GATES,"NOT_RUN"),"wire":[]}
    gates = report["gates"]
    gates["artifact_identity"] = "PASS"
    def bind(client):
        return partial(request,client,alias,wire=report["wire"],disable_thinking=True)
    binary = assets/"runtime/llama-cpp/cpu/llama-server.exe"
    with cpu_server(binary,model,port,target/"cpu.log",alias) as (client,build):
        gates["load"] = "PASS"
        gates["cpu_reference"] = "PASS" if chat_ok(bind(client)) else "FAIL"
        report["cpu"] = {"binary_sha256":digest(binary),"build":build}
    with gpu_server(engine/"llama-server.exe",model,"vulkan",server_environment(),target,
                    port,"vulkan",True,alias=alias) as (client,launch):
        expected = {**control,"engine":{**control["engine"],"layers":launch["layers_total"]},
                    "template":{"sha256":template}}
        verify_launch(launch,expected)
        report["gpu"] = launch
        test_gpu(bind(client),report)
    launch_file = target/"launch.json"
    write_json(launch_file,{**report["gpu"],"status":"PASS"})
    counter = target/report["gpu"]["counter_file"]
    gates["gpu_execution"] = "PASS" if verify_gpu({"gpu_launch":launch_file,"gpu_counters":counter},"vulkan") else "FAIL"
    public = target/"portable"
    public.mkdir()
    for name in (report["gpu"]["counter_file"],report["gpu"]["trace_file"]):
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
    parser.add_argument("candidate",choices=("M14","G31"))
    parser.add_argument("--assets",type=Path,default=ROOT.parent.parent)
    parser.add_argument("--out",type=Path,default=ROOT/".runtime/larger-judge-admission")
    parser.add_argument("--port",type=int,default=18745)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--verify-asset",action="store_true")
    action.add_argument("--download",action="store_true")
    parser.add_argument("--proxy")
    args = parser.parse_args()
    pin = next(r for r in json.loads(PINS.read_bytes())["candidates"] if r["code"] == args.candidate)
    if args.download:
        download(pin,args.assets.resolve(),args.proxy)
        print(pin["code"],pin["sha256"])
    elif args.verify_asset:
        local_asset(pin,args.assets.resolve())
        print(pin["code"],pin["sha256"])
    else:
        test(pin,args.assets.resolve(),args.out.resolve(),args.port)


if __name__ == "__main__":
    main()
