from mdcx.crawlers.dmm_direct import generate_cid_candidates, generate_image_candidates


def test_ipx_no_prefix_first():
    candidates = generate_cid_candidates("IPX-535")
    assert candidates[0] == "ipx00535"
    assert "ipx00535" in candidates


def test_abf_prefixed_candidate():
    candidates = generate_cid_candidates("ABF-042")
    assert "436abf00042" in candidates
    assert "abf00042" in candidates


def test_common_series_padded_five():
    candidates = generate_cid_candidates("SSIS-001")
    assert candidates == ["ssis00001"]
    assert generate_cid_candidates("MIDV-100") == ["midv00100"]


def test_special_threshold_small():
    assert "59avop00100" in generate_cid_candidates("AVOP-100")
    assert "59avop00001" in generate_cid_candidates("AVOP-1")


def test_special_threshold_large():
    assert "1avop00200" in generate_cid_candidates("AVOP-200")
    assert "h_860gigl00643" in generate_cid_candidates("GIGL-643")
    assert "gigl00644" in generate_cid_candidates("GIGL-644")


def test_prefix_group_members():
    candidates = generate_cid_candidates("DISM-123")
    assert candidates[0] == "1dism00123"
    candidates = generate_cid_candidates("HODV-001")
    assert "5642hodv00001" in candidates


def test_real_verified_prefixes():
    assert generate_cid_candidates("SW-123") == ["1sw00123", "sw00123", "h_113sw00123"]
    assert generate_cid_candidates("WANZ-100")[0] == "3wanz00100"
    assert generate_cid_candidates("NTRD-100")[0] == "18ntrd00100"
    assert generate_cid_candidates("PPD-100")[0] == "24ppd00100"
    assert generate_cid_candidates("UMD-100")[0] == "143umd00100"
    assert generate_cid_candidates("MBD-100")[0] == "433mbd00100"
    assert generate_cid_candidates("SIN-100")[0] == "118sin00100"
    assert generate_cid_candidates("YMD-100")[0] == "h_189ymd00100"
    assert generate_cid_candidates("MADM-100")[0] == "49madm00100"


def test_digit_series():
    candidates = generate_cid_candidates("T28-123")
    assert "55t2800123" in candidates
    assert "t2800123" in candidates
    assert generate_cid_candidates("T-2828") == generate_cid_candidates("T28-028")


def test_dedup_and_order():
    candidates = generate_cid_candidates("IPX-535")
    assert len(candidates) == len(set(candidates))


def test_invalid_number_returns_empty():
    assert generate_cid_candidates("") == []
    assert generate_cid_candidates("abc") == []
    assert generate_cid_candidates("12345") == []


def test_image_candidates_pairing():
    images = generate_image_candidates("IPX-535")
    assert len(images) == len(generate_cid_candidates("IPX-535")) * 2
    portrait = [o for o, _ in images if o == "portrait"]
    landscape = [o for o, _ in images if o == "landscape"]
    assert len(portrait) == len(landscape)
    for orient, url in images[:2]:
        assert url.startswith("https://awsimgsrc.dmm.co.jp/pics_dig/digital/video/")
        assert url.endswith(".jpg")
        if orient == "portrait":
            assert "ps.jpg" in url
        else:
            assert "pl.jpg" in url


def test_is_uncensored_number():
    from mdcx.crawlers.dmm_direct import is_uncensored_number

    assert is_uncensored_number("FC2-PPV-1234567")
    assert is_uncensored_number("HEYZO-0123")
    assert is_uncensored_number("CARIB_0421")
    assert not is_uncensored_number("SSIS-538")
    assert not is_uncensored_number("WANZ-100")
    assert not is_uncensored_number("")


def test_probe_discovered_prefixed_series():
    from mdcx.crawlers.dmm_direct import generate_cid_candidates

    expected = {
        "MILK-100": "h_1240milk00100",
        "HZGD-100": "h_1100hzgd00100",
        "FONE-100": "h_491fone00100",
        "BKD-100": "17bkd00100",
        "ONEZ-100": "118onez00100",
        "MADM-100": "49madm00100",
        "ABF-030": "436abf00030",
        "GG-100": "13gg00100",
        "GVG-100": "13gvg00100",
        "OVG-100": "13ovg00100",
    }
    for number, first_cid in expected.items():
        candidates = generate_cid_candidates(number)
        assert candidates[0] == first_cid, f"{number}: 首个候选 {candidates[0]} != {first_cid}"
        assert first_cid in candidates


def test_probe_discovered_prefix1_series():
    from mdcx.crawlers.dmm_direct import generate_cid_candidates

    for series in ["STARS", "START", "SDJS", "SDMT", "RCTD", "RCT", "FSDSS", "MMGH", "GS"]:
        candidates = generate_cid_candidates(f"{series}-100")
        assert candidates[0] == f"1{series.lower()}00100", f"{series}: {candidates[0]}"
        assert f"1{series.lower()}00100" in candidates
