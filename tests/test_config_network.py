from mdcx.config.models import Config


def test_config_update_normalizes_cf_bypass_proxy_scheme():
    data = {"cf_bypass_proxy": "127.0.0.1:7890"}

    Config.update(data)

    assert data["cf_bypass_proxy"] == "http://127.0.0.1:7890"


def test_config_update_keeps_cf_bypass_proxy_with_existing_scheme():
    data = {"cf_bypass_proxy": "socks5://127.0.0.1:7890"}

    Config.update(data)

    assert data["cf_bypass_proxy"] == "socks5://127.0.0.1:7890"


def test_config_model_dump_json_serializes_http_url_with_indent():
    data = Config().model_dump_json(indent=2)

    assert '"llm_url": "https://api.llm.com/v1"' in data


def test_proxy_hosts_list_default_off_parses_proxy_sites():
    cfg = Config(proxy_sites=" javdb.com , missav.ws ")

    assert cfg.proxy_hosts_list() == ["javdb.com", "missav.ws"]


def test_proxy_hosts_list_route_all_returns_wildcard():
    cfg = Config(proxy_sites="javdb.com", proxy_route_all=True)

    assert cfg.proxy_hosts_list() == ["*"]


def test_proxy_route_all_defaults_off():
    assert Config().proxy_route_all is False
