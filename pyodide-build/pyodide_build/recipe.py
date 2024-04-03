import functools
from collections.abc import Iterable
from pathlib import Path

from .io import MetaConfig
from .logger import logger


@functools.lru_cache(maxsize=1)
def load_all_recipes(recipe_dir: Path) -> dict[str, MetaConfig]:
    """Load all package recipes from the recipe directory."""

    recipes_path = recipe_dir.glob("*/meta.yaml")

    recipes: dict[str, MetaConfig] = {}
    for recipe in recipes_path:
        try:
            config = MetaConfig.from_yaml(recipe)
            recipes[config.package.name] = config
        except Exception as e:
            raise ValueError(f"Could not parse {recipe}.") from e

    return recipes


def load_recipes(
    recipe_dir: Path,
    names_or_tags: Iterable[str],
    load_always_tag: bool = True,
) -> dict[str, MetaConfig]:
    """
    Load the recipes for the given package names or tags.
    Note that this function does not do any dependency resolution.

    Parameters
    ----------
    recipe_dir
        Path to the recipe directory
    names_or_tags
        List of package names or tags to load.
        It also supports the following special values:
            - "*" : all packages
            - "no-numpy-dependents" : all packages except those that depend on numpy (including numpy itself)
    load_always_tag
        Whether to load packages with the "always" tag/

    Returns
    -------
    recipes
        Dictionary of package name => config
    """

    available_recipes = load_all_recipes(recipe_dir)

    # tag => list of recipes with that tag
    tagged_recipes: dict[str, list[MetaConfig]] = {}
    for recipe in available_recipes.values():
        for _tag in recipe.package.tag:
            tagged_recipes.setdefault(_tag, []).append(recipe)

    recipes: dict[str, MetaConfig] = {}

    for name_or_tag in names_or_tags:
        # 1. package name
        if name_or_tag in available_recipes:
            recipes[name_or_tag] = available_recipes[name_or_tag].model_copy(deep=True)

        # 2. tag
        elif (
            name_or_tag.startswith("tag:")
            and (tag := name_or_tag.removeprefix("tag:")) in tagged_recipes
        ):
            for recipe in tagged_recipes[tag]:
                recipes[recipe.package.name] = recipe.model_copy(deep=True)

        # 3. meta packages
        elif name_or_tag == "*":  # all packages
            recipes.update(
                {
                    name: package.model_copy(deep=True)
                    for name, package in available_recipes.items()
                }
            )
        elif name_or_tag == "no-numpy-dependents":
            # This is a meta package and will be handled outside of this function
            recipes["no-numpy-dependents"] = None  # type: ignore[assignment]

        elif name_or_tag in ("core", "min-scipy-stack"):
            logger.warning(
                f"Using meta package without the 'tag:' prefix is deprecated,"
                f" use 'tag:{name_or_tag}' instead."
            )
            for recipe in tagged_recipes[name_or_tag]:
                recipes[recipe.package.name] = recipe.model_copy(deep=True)
        else:
            raise ValueError(f"Unknown package name or tag: {name_or_tag}")

    if load_always_tag:
        always_recipes = tagged_recipes.get("always", [])
        for recipe in always_recipes:
            recipes[recipe.package.name] = recipe.model_copy(deep=True)

    return recipes
