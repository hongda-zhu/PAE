
import pytest

from ikusa.cra import CraArticle, CraMapper
from ikusa.models import MasvsCategory


def test_default_mapper_loads_known_categories():
    mapper = CraMapper.load_default()
    storage = mapper.articles_for(MasvsCategory.STORAGE)
    assert len(storage) >= 1
    assert all(isinstance(a, CraArticle) for a in storage)
    assert any("Annex I" in a.id for a in storage)


def test_short_label_for_known_category():
    mapper = CraMapper.load_default()
    label = mapper.short_label_for(MasvsCategory.NETWORK)
    assert label.startswith("Art.")


def test_unknown_category_in_empty_mapper_returns_empty():
    mapper = CraMapper(mapping={})
    assert mapper.articles_for(MasvsCategory.STORAGE) == []


def test_unknown_category_short_label_has_fallback():
    mapper = CraMapper(mapping={})
    label = mapper.short_label_for(MasvsCategory.STORAGE)
    assert "Art." in label


def test_load_from_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        CraMapper.load_from(tmp_path / "does_not_exist.yaml")


def test_load_from_custom_yaml(tmp_path):
    yaml_path = tmp_path / "custom.yaml"
    yaml_path.write_text(
        "MASVS-STORAGE:\n"
        "  article_short: 'Custom Art. X'\n"
        "  cra_articles:\n"
        "    - id: 'X.1'\n"
        "      title: 'Custom requirement'\n"
    )
    mapper = CraMapper.load_from(yaml_path)
    articles = mapper.articles_for(MasvsCategory.STORAGE)
    assert len(articles) == 1
    assert articles[0].id == "X.1"
    assert mapper.short_label_for(MasvsCategory.STORAGE) == "Custom Art. X"


def test_all_eight_masvs_categories_mapped_in_default():
    mapper = CraMapper.load_default()
    for cat in MasvsCategory:
        assert mapper.articles_for(cat), f"{cat.value} has no CRA articles"
        assert mapper.short_label_for(cat) != ""
