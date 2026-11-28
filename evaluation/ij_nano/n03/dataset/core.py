"""N03 dataset core (IJ-NANO-1.3S N03-B2): case specification, bilingual
world infrastructure and roster assembly.

Design contracts (continuation order sections 4-6):
- every case carries an explicit output-contract reference; representations
  differ per primitive (no generic-JSON flattening of C09/C10/C11/C07/C31);
- families are the split unit: a family appears in development OR
  confirmation, never both (family-level separation, not paraphrase splits);
- public payloads carry NO answer material; expectations live in separate
  artifacts (dev committed, confirmation protected/local-only);
- generation is deterministic given seeds; confirmation seeds are NOT
  committed (answer-bearing), only their SHA256 manifest is.
"""
from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass, field

LANGS = ("en", "zh")
SPLIT_DEV = "development"
SPLIT_CONF = "confirmation"


@dataclass
class Case:
    case_id: str                 # n03-<prim>-<fam>-<split-letter><seq>
    primitive: str               # C01..C32
    family: str                  # family id, unique per primitive
    world: str                   # world id (shared across families for clustering)
    split: str                   # development | confirmation
    language: str                # en | zh
    difficulty: int              # 1..3
    public_payload: dict         # model-facing; MUST NOT contain answers
    contract_ref: str            # primitive output contract (taxonomy)
    protocols: list              # applicable protocol ids (taxonomy vocab)
    expected: dict               # ground truth (never in public artifacts)
    alternatives: list           # declared-equivalent accepted answers
    family_witnesses: dict       # positive/negative raw-response exemplars

    def public_view(self) -> dict:
        return {"case_id": self.case_id, "primitive": self.primitive,
                "family": self.family, "world": self.world,
                "split": self.split, "language": self.language,
                "difficulty": self.difficulty,
                "public_payload": self.public_payload,
                "contract_ref": self.contract_ref,
                "protocols": self.protocols}


@dataclass
class Family:
    """A task family: one world, one parametrized semantic operation."""
    family_id: str
    primitive: str
    world: str
    split: str
    protocols: list
    build: object                 # callable(rng, language, seq) -> CaseParams
    witnesses: dict               # {"positive": [...], "negative": [...]}

    def emit(self, rng: random.Random, language: str, seq: int) -> Case:
        params = self.build(rng, language, seq)
        diff = params.pop("difficulty")
        pub, exp, alts = params["public"], params["expected"], \
            params.get("alternatives", [])
        return Case(
            case_id=f"n03-{self.primitive}-{self.family_id}-"
                    f"{'d' if self.split == SPLIT_DEV else 'c'}{seq:02d}",
            primitive=self.primitive, family=self.family_id,
            world=self.world, split=self.split, language=language,
            difficulty=diff, public_payload=pub,
            contract_ref=f"{self.primitive}:output_contract",
            protocols=list(self.protocols), expected=exp,
            alternatives=alts, family_witnesses=self.witnesses)


# -- shared bilingual world content ---------------------------------------
# Entity pools are world-scoped; ids are stable ASCII slugs, surface names
# are per-language. Distinct families draw disjoint entity subsets so that
# confirmation families never reuse development entity identities.

WORLDS = {
    "helpdesk": {
        "en": {"agents": ["Priya Natarajan", "Marcus Feld", "Sofia Reyes"],
               "systems": ["billing-portal", "fleet-tracker", "crm-hub"],
               "tickets": ["TCK-4109", "TCK-5233", "TCK-6118"]},
        "zh": {"agents": ["李伟", "赵敏", "陈静"], 
               "systems": ["计费门户", "车队追踪", "客户管理"],
               "tickets": ["工单4109", "工单5233", "工单6118"]}},
    "smart_home": {
        "en": {"rooms": ["study", "sunroom", "hallway"],
               "devices": ["air purifier", "motorized blind", "towel warmer"],
               "members": ["Dana", "Ravi", "Mei"]},
        "zh": {"rooms": ["书房", "阳光房", "走廊"],
               "devices": ["空气净化器", "电动窗帘", "毛巾加热架"],
               "members": ["小丹", "小瑞", "小美"]}},
    "retail_ops": {
        "en": {"stores": ["harbor-outlet", "midtown-flagship", "north-depot"],
               "items": ["trail jacket", "insulated bottle", "camp stool"],
               "members": ["Dana", "Ravi", "Mei"],
               "currencies": ["JPY", "USD", "EUR"]},
        "zh": {"stores": ["海港折扣店", "城中旗舰店", "北仓"],
               "items": ["冲锋衣", "保温壶", "露营凳"],
               "members": ["小丹", "小瑞", "小美"],
               "currencies": ["JPY", "USD", "EUR"]}},
    "logistics": {
        "en": {"hubs": ["KRK-2", "LIS-1", "OSA-4"],
               "parcels": ["PKG-77120", "PKG-88401", "PKG-90317"],
               "modes": ["air freight", "rail", "courier van"]},
        "zh": {"hubs": ["克拉科夫2号仓", "里斯本1号仓", "大阪4号仓"],
               "parcels": ["包裹77120", "包裹88401", "包裹90317"],
               "modes": ["空运", "铁路", "专车"]}},
    "clinic": {
        "en": {"patients": ["A. Okafor", "J. Lindqvist", "H. Tanaka"],
               "departments": ["cardiology", "dermatology", "physiotherapy"],
               "slots": ["09:20", "11:45", "14:10"]},
        "zh": {"patients": ["奥卡福", "林德奎斯特", "田中"],
               "departments": ["心内科", "皮肤科", "理疗科"],
               "slots": ["09:20", "11:45", "14:10"]}},
    "finance_backoffice": {
        "en": {"accounts": ["ACC-2210", "ACC-3308", "ACC-4471"],
               "analysts": ["Tomas Vidal", "Ines Kaur", "Paul Eshun"],
               "ledgers": ["AP", "AR", "TAX"]},
        "zh": {"accounts": ["账户2210", "账户3308", "账户4471"],
               "analysts": ["托马斯·维达尔", "伊内斯·考尔", "保罗·埃顺"],
               "ledgers": ["应付", "应收", "税务"]}},
}


def digest_obj(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True,
                                     ensure_ascii=False).encode(
        "utf-8")).hexdigest()


def roster_digest(cases: list[Case]) -> str:
    return digest_obj([c.public_view() for c in cases])


def expected_digest(cases: list[Case]) -> str:
    return digest_obj([{ "case_id": c.case_id, "expected": c.expected,
                         "alternatives": c.alternatives}
                        for c in cases])


def split_lang_counts(cases: list[Case]) -> dict:
    out: dict = {}
    for c in cases:
        out[(c.split, c.language)] = out.get((c.split, c.language), 0) + 1
    return {f"{s}:{l}": n for (s, l), n in sorted(out.items())}
