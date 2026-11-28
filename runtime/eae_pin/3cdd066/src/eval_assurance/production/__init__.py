"""Production evaluation leg (EA04/EA05): the dataset-consumer side of the
dual-path integration — ProductionParser + ProductionEvaluator over STORED
expectation records, mirroring what the physical runner scores trials with."""
from .parser import ProductionParser, ParsedAnswer, parse_response
from .evaluator import ProductionEvaluator, ProductionVerdict

__all__ = ["ProductionParser", "ParsedAnswer", "parse_response",
           "ProductionEvaluator", "ProductionVerdict"]
