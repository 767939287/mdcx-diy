from lxml import etree

from mdcx.crawlers import fc2, jav321, mgstage


def test_fc2_tags_keep_quotes_and_brackets():
    html = etree.HTML('<a class="tag tagTag">[限定]</a><a class="tag tagTag">O\'Brien</a>')

    assert fc2.getTag(html) == "[限定],O'Brien"


def test_jav321_fields_keep_quotes_and_brackets():
    response = """
    <h3>[Director's Cut] <small></small></h3>
    <b>出演者</b>: O'Brien [Guest] &nbsp; <br>
    <b>収録時間</b>: 120 分<br>
    <b>配信開始日</b>: 2024-01-01<br>
    <b>平均評価</b>: 4.5<br>
    """
    html = etree.HTML(
        '<div class="col-md-9"><a href="/company/test">[Studio]</a><a href="/series/test">O\'Brien</a></div>'
    )

    assert jav321.getTitle(response) == "[Director's Cut]"
    assert jav321.getActor(response) == "O'Brien [Guest]"
    assert jav321.getRuntime(response) == "120"
    assert jav321.getRelease(response) == "2024-01-01"
    assert jav321.getScore(response) == "4.5"
    assert jav321.getStudio(html) == "[Studio]"
    assert jav321.getSeries(html) == "O'Brien"


def test_mgstage_fields_join_multiple_values_without_list_syntax():
    html = etree.HTML(
        """
        <div id="center_column"><div><h1>[Title] O'Brien</h1></div></div>
        <table>
          <tr><th>出演</th><td><a>[Actor]</a><a>O'Brien</a></td></tr>
          <tr><th>メーカー：</th><td><a>[Studio]</a></td></tr>
          <tr><th>ジャンル：</th><td><a>[Tag]</a><a>O'Brien</a></td></tr>
        </table>
        <a id="EnlargeImage" href="https://example.test/[cover].jpg" />
        """
    )

    assert mgstage.getTitle(html) == "[Title] O'Brien"
    assert mgstage.getActor(html) == "[Actor],O'Brien"
    assert mgstage.getStudio(html) == "[Studio]"
    assert mgstage.getTag(html) == "[Tag],O'Brien"
    assert mgstage.getCover(html) == "https://example.test/[cover].jpg"
