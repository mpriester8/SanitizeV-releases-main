import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

import log_tailer  # noqa: E402


def test_classify_levels():
    assert log_tailer.classify("Resource started: oxmysql").level == "success"
    assert log_tailer.classify("[ERROR] script crashed").level == "error"
    assert log_tailer.classify("Warning: deprecated").level == "warning"
    assert log_tailer.classify("hello world").level == "info"


def test_classify_resource_extracted():
    line = log_tailer.classify("[ script:es_extended] something")
    assert line.resource == "es_extended"
    plain = log_tailer.classify("no resource here")
    assert plain.resource is None
