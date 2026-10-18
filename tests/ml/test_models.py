import pytest

pytestmark = [pytest.mark.unit, pytest.mark.ml]
torch = pytest.importorskip("torch")
onnx = pytest.importorskip("onnx")
ort = pytest.importorskip("onnxruntime")


def test_patch_forecaster_shape_and_export_parity(tmp_path):
    from backend.ml.baseline.export_onnx import export_model
    from backend.ml.baseline.forecaster import PatchForecaster

    torch.set_num_threads(1)
    torch.manual_seed(19)
    model = PatchForecaster().eval()
    values = torch.zeros((1, 1440, 5))
    with torch.no_grad():
        assert tuple(model(values).shape) == (1, 60, 5)
    torch.save(model.state_dict(), tmp_path / "forecaster.pt")
    assert export_model(tmp_path) < 1e-4


def test_sequence_transformer_shape():
    from backend.ml.anomaly.seq_model import SequenceTransformer

    model = SequenceTransformer(20).eval()
    with torch.no_grad():
        assert tuple(model(torch.zeros((2, 64), dtype=torch.long)).shape) == (2, 64, 20)
