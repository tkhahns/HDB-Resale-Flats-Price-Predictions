"""Tests for src.avm.io.storage — local round-trips for all helpers."""

import json

import numpy as np
import pytest

from src.avm.io.storage import (
    exists,
    load_joblib,
    makedirs,
    read_json,
    read_text,
    save_joblib,
    savefig,
    write_json,
    write_text,
)


def test_makedirs_creates_nested(tmp_path):
    target = str(tmp_path / "a" / "b" / "c" / "file.txt")
    makedirs(target)
    assert (tmp_path / "a" / "b" / "c").is_dir()


def test_makedirs_directory_path(tmp_path):
    target = str(tmp_path / "mydir" / "subdir" / "")
    makedirs(target)
    assert (tmp_path / "mydir" / "subdir").is_dir()


def test_makedirs_noop_for_s3():
    makedirs("s3://some-bucket/path/to/file.pkl")  # must not raise


def test_exists_true(tmp_path):
    f = tmp_path / "exists.txt"
    f.write_text("hi")
    assert exists(str(f)) is True


def test_exists_false(tmp_path):
    assert exists(str(tmp_path / "nope.txt")) is False


def test_write_read_text(tmp_path):
    path = str(tmp_path / "hello.txt")
    write_text(path, "hello world")
    assert read_text(path) == "hello world"


def test_write_read_json(tmp_path):
    path = str(tmp_path / "data.json")
    data = {"a": 1, "b": [1, 2, 3]}
    write_json(data, path)
    loaded = read_json(path)
    assert loaded == data


def test_save_load_joblib_array(tmp_path):
    path = str(tmp_path / "arr.pkl")
    arr = np.array([1.0, 2.0, 3.0])
    save_joblib(arr, path)
    loaded = load_joblib(path)
    np.testing.assert_array_equal(arr, loaded)


def test_save_load_joblib_dict(tmp_path):
    path = str(tmp_path / "sub" / "obj.pkl")
    obj = {"key": "value", "nums": [1, 2, 3]}
    save_joblib(obj, path)
    loaded = load_joblib(path)
    assert loaded == obj


def test_savefig_creates_file(tmp_path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots()
    ax.plot([1, 2, 3], [4, 5, 6])
    path = str(tmp_path / "plot.png")
    savefig(plt, path)
    plt.close()
    assert exists(path)
    assert (tmp_path / "plot.png").stat().st_size > 0


def test_write_json_creates_parent_dirs(tmp_path):
    path = str(tmp_path / "nested" / "deep" / "data.json")
    write_json({"x": 42}, path)
    assert read_json(path) == {"x": 42}
