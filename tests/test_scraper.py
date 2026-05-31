import pytest
from scraper import clean_club_name, parse_html, CITY_MAP
from datetime import datetime, timezone


SAMPLE_HTML = """
<div class="clubs-occupancy-block">
  <div class="container">
    <h5 class="text-uppercase mb-16">Šiaulių klubai</h5>
    <div class="clubs-occupancies">
      <div class="clubs-occupancy">
        <div class="clubs-occupancy__club">
          <h6 class="xs-small text-uppercase mb-0">Šiaulių Akropolis - naujas✨</h6>
          <p class="mb-0">Aido g. 8, Šiauliai</p>
        </div>
        <h6 class="clubs-occupancy__percentage clubs-occupancy__percentage--success">10%</h6>
      </div>
    </div>

    <h5 class="text-uppercase mb-16">Kauno klubai</h5>
    <div class="clubs-occupancies">
      <div class="clubs-occupancy">
        <div class="clubs-occupancy__club">
          <h6 class="xs-small text-uppercase mb-0">Šilainiai</h6>
          <p class="mb-0">Baltų pr. 16, Kaunas</p>
        </div>
        <h6 class="clubs-occupancy__percentage clubs-occupancy__percentage--success">17%</h6>
      </div>
      <div class="clubs-occupancy">
        <div class="clubs-occupancy__club">
          <h6 class="xs-small text-uppercase mb-0">Savanoriai</h6>
          <p class="mb-0">Savanorių pr. 263, Kaunas</p>
        </div>
        <h6 class="clubs-occupancy__percentage clubs-occupancy__percentage--warning">65%</h6>
      </div>
    </div>

    <h5 class="text-uppercase mb-16">Vilniaus klubai</h5>
    <div class="clubs-occupancies">
      <div class="clubs-occupancy">
        <div class="clubs-occupancy__club">
          <h6 class="xs-small text-uppercase mb-0">Pilaitė (atnaujintas✨)</h6>
          <p class="mb-0">Vydūno g. 2, Vilnius</p>
        </div>
        <h6 class="clubs-occupancy__percentage clubs-occupancy__percentage--success">14%</h6>
      </div>
      <div class="clubs-occupancy">
        <div class="clubs-occupancy__club">
          <h6 class="xs-small text-uppercase mb-0">Rišė - jau greitai 🔜</h6>
          <p class="mb-0">Rišės g. 1, Vilnius</p>
        </div>
        <h6 class="clubs-occupancy__percentage clubs-occupancy__percentage--danger">100%</h6>
      </div>
      <div class="clubs-occupancy">
        <div class="clubs-occupancy__club">
          <h6 class="xs-small text-uppercase mb-0">Europa</h6>
          <p class="mb-0">Europebos g. 5, Vilnius</p>
        </div>
        <h6 class="clubs-occupancy__percentage clubs-occupancy__percentage--warning">42%</h6>
      </div>
    </div>
  </div>
</div>
"""


class TestCleanClubName:
    def test_strips_naujas(self):
        assert clean_club_name("Akropolis - naujas✨") == "Akropolis"

    def test_strips_atnaujintas(self):
        assert clean_club_name("Pilaitė (atnaujintas✨)") == "Pilaitė"

    def test_strips_jau_greitai(self):
        assert clean_club_name("Rišė - jau greitai 🔜") == "Rišė"

    def test_strips_isolated_emoji(self):
        assert clean_club_name("Club✨") == "Club"

    def test_plain_name_unchanged(self):
        assert clean_club_name("Europa") == "Europa"

    def test_strips_whitespace(self):
        assert clean_club_name("  Europa  ") == "Europa"

    def test_strips_new(self):
        assert clean_club_name("Club NEW") == "Club"

    def test_strips_new_parens(self):
        assert clean_club_name("Club (new)") == "Club"

    def test_combined_tags(self):
        result = clean_club_name("Test - naujas✨ (atnaujintas✨)")
        assert "naujas" not in result
        assert "atnaujintas" not in result


class TestParseHtml:
    def test_parses_all_clubs(self):
        records = parse_html(SAMPLE_HTML)
        assert len(records) == 6

    def test_city_assignment(self):
        records = parse_html(SAMPLE_HTML)
        siauliai = [r for r in records if r["city"] == "Šiauliai"]
        kaunas = [r for r in records if r["city"] == "Kaunas"]
        vilnius = [r for r in records if r["city"] == "Vilnius"]
        assert len(siauliai) == 1
        assert len(kaunas) == 2
        assert len(vilnius) == 3

    def test_club_names_cleaned(self):
        records = parse_html(SAMPLE_HTML)
        names = [r["club_name"] for r in records]
        assert "Šiaulių Akropolis" in names
        assert "Pilaitė" in names
        assert "Rišė" in names
        for name in names:
            assert "✨" not in name
            assert "🔜" not in name

    def test_addresses_extracted(self):
        records = parse_html(SAMPLE_HTML)
        by_name = {r["club_name"]: r for r in records}
        assert by_name["Šilainiai"]["address"] == "Baltų pr. 16, Kaunas"
        assert by_name["Pilaitė"]["address"] == "Vydūno g. 2, Vilnius"

    def test_percentages_extraced(self):
        records = parse_html(SAMPLE_HTML)
        by_name = {r["club_name"]: r for r in records}
        assert by_name["Šiaulių Akropolis"]["usage_percentage"] == 10
        assert by_name["Savanoriai"]["usage_percentage"] == 65
        assert by_name["Rišė"]["usage_percentage"] == 100
        assert by_name["Europa"]["usage_percentage"] == 42

    def test_timestamps_are_utc(self):
        records = parse_html(SAMPLE_HTML)
        for r in records:
            assert isinstance(r["timestamp"], datetime)
            assert r["timestamp"].tzinfo == timezone.utc

    def test_required_keys(self):
        records = parse_html(SAMPLE_HTML)
        for r in records:
            assert "club_name" in r
            assert "city" in r
            assert "address" in r
            assert "usage_percentage" in r
            assert "timestamp" in r

    def test_empty_html(self):
        records = parse_html("<html><body></body></html>")
        assert records == []

    def test_html_without_occupancy_block(self):
        html = "<html><body><h5>Kauno klubai</h5><p>Some text</p></body></html>"
        records = parse_html(html)
        assert records == []


class TestCityMap:
    def test_all_cities_present(self):
        assert "Šiaulių klubai" in CITY_MAP
        assert "Kauno klubai" in CITY_MAP
        assert "Vilniaus klubai" in CITY_MAP

    def test_values(self):
        assert CITY_MAP["Šiaulių klubai"] == "Šiauliai"
        assert CITY_MAP["Kauno klubai"] == "Kaunas"
        assert CITY_MAP["Vilniaus klubai"] == "Vilnius"