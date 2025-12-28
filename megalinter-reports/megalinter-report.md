## ✅⚠️[MegaLinter](https://megalinter.io/9.2.0) analysis: Success with warnings



|Descriptor |                                   Linter                                    |Files|Fixed|Errors|Warnings|Elapsed time|
|-----------|-----------------------------------------------------------------------------|----:|----:|-----:|-------:|-----------:|
|⚠️ MARKDOWN|[markdownlint](https://megalinter.io/9.2.0/descriptors/markdown_markdownlint)|    2|    0|     2|       0|       0.78s|
|✅ PYTHON  |[black](https://megalinter.io/9.2.0/descriptors/python_black)                |    1|    1|     0|       0|       0.79s|
|✅ PYTHON  |[isort](https://megalinter.io/9.2.0/descriptors/python_isort)                |    1|    1|     0|       0|       0.16s|
|✅ PYTHON  |[pylint](https://megalinter.io/9.2.0/descriptors/python_pylint)              |    1|     |     0|       0|       5.07s|
|✅ YAML    |[prettier](https://megalinter.io/9.2.0/descriptors/yaml_prettier)            |    9|    0|     0|       0|       0.71s|
|✅ YAML    |[yamllint](https://megalinter.io/9.2.0/descriptors/yaml_yamllint)            |    9|     |     0|       0|       0.36s|

## Detailed Issues

<details>
<summary>⚠️ MARKDOWN / markdownlint - 2 errors</summary>

```
README-bak.md:1 MD041/first-line-heading/first-line-h1 First line in a file should be a top-level heading [Context: "<div align="center">"]
README.md:1 MD041/first-line-heading/first-line-h1 First line in a file should be a top-level heading [Context: "<div align="center">"]
```

</details>

See detailed reports in MegaLinter artifacts

You could have the same capabilities but better runtime performances if you use a MegaLinter flavor:
- [oxsecurity/megalinter/flavors/python@v9.2.0](https://megalinter.io/9.2.0/flavors/python/) (65 linters)
- [oxsecurity/megalinter/flavors/cupcake@v9.2.0](https://megalinter.io/9.2.0/flavors/cupcake/) (88 linters)


Your project could benefit from a custom flavor, which would allow you to run only the linters you need, and thus improve runtime performances. (Skip this info by defining `FLAVOR_SUGGESTIONS: false`)

  - Documentation: [Custom Flavors](https://megalinter.io/9.2.0/custom-flavors/)
  - Command: `npx mega-linter-runner@9.2.0 --custom-flavor-setup --custom-flavor-linters PYTHON_PYLINT,PYTHON_BLACK,PYTHON_ISORT,MARKDOWN_MARKDOWNLINT,YAML_PRETTIER,YAML_YAMLLINT`

[![MegaLinter is graciously provided by OX Security](https://raw.githubusercontent.com/oxsecurity/megalinter/main/docs/assets/images/ox-banner.png)](https://www.ox.security/?ref=megalinter)