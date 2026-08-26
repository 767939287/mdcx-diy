from lxml import etree

from mdcx.crawlers import fc2, fc2club, fc2hub, javlibrary, mgstage


def test_fc2_tags_keep_quotes_and_brackets():
    html = etree.HTML('<a class="tag tagTag">[限定]</a><a class="tag tagTag">O\'Brien</a>')

    assert fc2.getTag(html) == "[限定],O'Brien"


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


def test_fc2club_and_fc2hub_preserve_special_text_and_empty_fields():
    club_html = etree.HTML(
        "<p><strong>女优名字</strong><a>[Actor]</a><a>O'Brien</a></p>"
        "<p><strong>影片标签</strong><a>[Tag]</a><a>O'Brien</a></p>"
        '<div class="col des">[Outline] O\'Brien</div>'
    )
    hub_html = etree.HTML(
        '<h1>FC2-1</h1><p class="card-text"><a href="/tag/a">[Tag]</a><a href="/tag/b">O\'Brien</a></p>'
    )

    assert fc2club.getActor(club_html, "seller") == "[Actor],O'Brien"
    assert fc2club.getTag(club_html) == "[Tag],O'Brien"
    assert fc2club.getOutline(club_html) == "[Outline] O'Brien"
    assert fc2hub.getTitle(hub_html) == ""
    assert fc2hub.getStudio(hub_html) == ""
    assert fc2hub.getTag(hub_html) == "[Tag],O'Brien"


def test_javlibrary_preserves_special_actor_tag_and_release_text():
    html = etree.HTML(
        '<div id="video_cast"><span class="star"><a>[Actor]</a><a>O\'Brien</a></span></div>'
        '<div id="video_genres"><td class="text"><span><a>[Tag]</a><a>O\'Brien</a></span></td></div>'
        '<div id="video_date"><td class="text">[2026-04-03]</td></div>'
    )

    assert javlibrary.get_actor(html) == "[Actor],O'Brien"
    assert javlibrary.get_tag(html) == "[Tag],O'Brien"
    assert javlibrary.get_release(html) == "[2026-04-03]"
