# Introduction

Hi there, and thank you for considering contributing to `kmermaid` to help us make our code a better version of itself!

`kmermaid` is an open source project, and as such any kind of contribution is welcome! There are many ways in which you can contribute: improve the code or the documentation, submit bug reports, request new features or write tutorials or blog posts.

# Ground Rules

To see what kinds of behaviour are acceptable when contributing to `kmermaid`, please refer to our [code of conduct](https://github.com/ggirelli/kmermaid/blob/main/CODE_OF_CONDUCT.md).

# Getting started

We host `kmermaid` on github, where we also track issues and feature requests, as well as handle pull requests.

Please, note that any contributions you make will be under the MIT Software License. In other words, all your submissions are understood to be under the same [MIT License](http://choosealicense.com/licenses/mit/) that covers the `kmermaid` project. Feel free to contact us if that's a concern.

## How to submit a contribution

To process code change, we follow the [Github Flow](https://guides.github.com/introduction/flow/index.html). All code changes to our `main` branch happen through pull requests from the `dev` branch. We actively welcome your pull requests to the `dev` branch!

## How to report a bug

If you want to report a **bug**, please use the github [issue tracker](https://github.com/ggirelli/kmermaid/issues) and follow the issue template that should automatically show up.

## How to suggest a feature or enhancement

If you would like to see a new feature implemented in `kmermaid`, or to have an already existing feature improved, please use the github [issue tracker](https://github.com/ggirelli/kmermaid/issues) and follow the template that should automatically show up.

# Style your contributions

We like to have `kmermaid`'s code styled with [`black`](https://github.com/psf/black) and checked with `mypy`.

`mypy`, `flake8`, and `black` conforming checks are automatically ran on all pull requests through GitHub Actions and can be run locally using `pre-commit`.

Docstrings should be included, when possible. Please use `sphinx` as your docstring's style. Also, all docstrings should pass a check with `darglint`.

Finally, all imports should be sorted using `isort -m 3 --tc`, which is also included as a `pre-commit` hook.

# Changing dependencies

If your code changes `kmermaid` dependencies, we recommend to change them in the `pyproject.toml` file. See [poetry](https://github.com/python-poetry/poetry)'s documentation for more details on the format of the `pyproject.toml` file.
