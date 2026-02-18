import backend_modules as bm


def test_mask_email():
    assert bm._mask_email("sample@gmail.com") == "s.....@gmail.com"
    assert bm._mask_email("a@x.com") == "a.....@x.com"
    assert bm._mask_email(None) is None


def test_mask_phone():
    assert bm._mask_phone("+34 666 123 5810") == "...5810"
    assert bm._mask_phone("5810") == "...5810"
    assert bm._mask_phone(None) is None


def test_diagnose_from_matches():
    assert "Interposer" in bm._diagnose_from_matches(["SMC Panic"])
    assert "Watchdog" in bm._diagnose_from_matches(["WDT Timeout"])
    assert "0x800" in bm._diagnose_from_matches(["0x800"]) or "baseband" in bm._diagnose_from_matches(["0x800"]).lower()
    assert "No se encontraron" in bm._diagnose_from_matches([])
