from pathlib import Path

import pytest

from pyodide_build import recipe

RECIPE_DIR = Path(__file__).parent / "_test_recipes"


def test_load_all_recipes():
    recipes = recipe.load_all_recipes(RECIPE_DIR)

    assert recipes
    assert "pkg_test_graph1" in recipes
    assert "pkg_test_graph2" in recipes


def test_load_recipes_basic():
    recipes = recipe.load_recipes(RECIPE_DIR, {"pkg_test_graph1", "pkg_test_graph2"})

    assert "pkg_test_graph1" in recipes
    assert "pkg_test_graph2" in recipes
    assert "pkg_test_graph3" not in recipes


def test_load_recipes_tag():
    recipes = recipe.load_recipes(RECIPE_DIR, {"tag:test_tag"})

    assert "pkg_test_tag" in recipes


def test_load_recipes_always():
    recipes = recipe.load_recipes(RECIPE_DIR, set(), load_always_tag=True)

    assert "pkg_test_tag_always" in recipes

    recipes = recipe.load_recipes(RECIPE_DIR, set(), load_always_tag=False)

    assert "pkg_test_tag_always" not in recipes


def test_load_recipes_all():
    recipes = recipe.load_recipes(RECIPE_DIR, {"*"})

    assert "pkg_test_graph1" in recipes


def test_load_recipes_no_numpy_dependents():
    recipes = recipe.load_recipes(RECIPE_DIR, {"no-numpy-dependents"})

    assert "no-numpy-dependents" in recipes


def test_load_recipes_invalid():
    pytest.raises(ValueError, recipe.load_recipes, RECIPE_DIR, {"invalid"})
