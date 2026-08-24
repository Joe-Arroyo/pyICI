# Contributing to pyICI

Thank you for your interest in contributing to pyICI!

## Reporting issues

If you find a bug or have a problem using pyICI, please
[open an issue](https://github.com/Joe-Arroyo/pyICI/issues) and include:

- What you were trying to do and what happened instead
- Your operating system and Python version
- The exact error message or a screenshot, if applicable
- If possible, a small data file that reproduces the problem (or a description
  of your data format — number of columns, units, number of cycles)

## Seeking support

Questions about how to use pyICI (input file format, choosing a regression
window, interpreting *R* and *k*, etc.) are also welcome as
[issues](https://github.com/Joe-Arroyo/pyICI/issues). Please read the
[README](README.md) and [Tutorial](Tutorial.md) first.

## Contributing code

Contributions are welcome via pull requests:

1. Fork the repository and create a branch for your change.
2. Make your changes. Keep the separation between the `analysis` modules
   (computation) and the `gui` modules (presentation).
3. Verify that the application still runs (`python main_gui.py`) and that the
   example datasets in [`data/`](data) load and analyze correctly through all
   tabs.
4. Open a pull request describing what the change does and why.

For larger changes (new analysis features, new input formats), please open an
issue first to discuss the idea.

## License

By contributing, you agree that your contributions will be licensed under the
[MIT License](LICENSE).
