from voa_inventory.robots import RobotsRules

VOA = """
Sitemap: https://learningenglish.voanews.com/sitemap.xml

User-agent:*
Disallow: /z/*/*/*/*
Disallow: /*?p=*
Disallow: /comments/*
Disallow: /s?k=*

User-agent: AhrefsBot
Disallow: /

User-agent: RavenCrawler
Allow: /
"""


def rules(agent: str = "sonari-voa-inventory/0.1") -> RobotsRules:
    return RobotsRules.parse(VOA, agent)


def test_article_pages_are_allowed() -> None:
    assert rules().allowed("/a/watching-the-grass-grow-is-not-fun/8003108.html")
    assert rules().allowed("/a/8197492.html")
    assert rules().allowed("/z/987")


def test_wildcard_rules_block_dated_archives_pagination_and_search() -> None:
    assert not rules().allowed("/z/987/2025/03/15/x")
    assert not rules().allowed("/z/987?p=2")
    assert not rules().allowed("/comments/123")
    assert not rules().allowed("/s?k=grass")


def test_named_group_wins_over_star_group() -> None:
    assert not RobotsRules.parse(VOA, "Mozilla AhrefsBot/7").allowed("/a/1.html")
    assert RobotsRules.parse(VOA, "RavenCrawler").allowed("/z/987?p=2")


def test_longest_rule_wins_and_allow_wins_a_tie() -> None:
    text = "User-agent: *\nDisallow: /a/\nAllow: /a/ok\nDisallow: /b\nAllow: /b\n"
    r = RobotsRules.parse(text, "x")
    assert r.allowed("/a/ok.html")
    assert not r.allowed("/a/no.html")
    assert r.allowed("/b/anything")


def test_dollar_anchors_the_end() -> None:
    r = RobotsRules.parse("User-agent: *\nDisallow: /*.pdf$\n", "x")
    assert not r.allowed("/files/x.pdf")
    assert r.allowed("/files/x.pdf.html")


def test_empty_file_allows_everything() -> None:
    assert RobotsRules.parse("", "x").allowed("/anything")
