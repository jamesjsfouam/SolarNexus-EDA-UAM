from solarnexus.__main__ import main


def test_demo_laborable(capsys):
    assert main(["--dias", "30"]) == 0
    salida = capsys.readouterr().out
    assert "Tb elegida por AIC" in salida
    assert "peak_shaving" in salida or "carga" in salida


def test_demo_fin_de_semana_exporta(capsys):
    assert main(["--dias", "30", "--dia", "finde"]) == 0
    assert "exportacion" in capsys.readouterr().out
