import ast
import importlib
import os
import sys
import yaml

from pathlib import Path


# Root of pipelines repo
BASE_DIR = str(Path(__file__).parent.parent.absolute())


def is_bids_app(path):
    """
    Check if this python file looks like a bids app

    i.e. contains `spec` and `task` as top level variables
    """

    with open(path, "r") as f:
        data = ast.parse(f.read())

    top_level_vars = {x.id for y in data.body if type(y) is ast.Assign for x in y.targets}

    return {"spec", "task"} <= top_level_vars


def escaped(value: str) -> str:
    if not value:
        return ""
    return f"`{value}`"


class MarkdownTable:
    def __init__(self, f, *headers: str) -> None:
        self.headers = tuple(headers)

        self.f = f
        self._write_header()

    def _write_header(self):
        self.write_row(*self.headers)
        self.write_row(*("-" * len(x) for x in self.headers))

    def write_row(self, *cols: str):
        cols = list(cols)
        if len(cols) > len(self.headers):
            raise ValueError(f"More entries in row ({len(cols)} than columns ({len(self.headers)})")

        # pad empty column entries if there's not enough
        cols += [""] * (len(self.headers) - len(cols))

        # TODO handle new lines in col
        self.f.write("|" + "|".join(col.replace("|", "\\|") for col in cols) + "|\n")


def parse_bids_app(path, output_dir):
    module_name = path.replace(".py", "").replace("/", ".")
    print(module_name)
    mod = importlib.import_module(module_name)

    task, metadata = mod.task, mod.spec

    fn = os.path.join(output_dir, os.path.basename(metadata["package_name"]) + ".md")

    header = {
        "title": metadata["package_name"],
        "weight": 10,
        "source_file": path.replace(BASE_DIR, ""),
    }

    with open(fn, "w") as f:
        f.write("---\n")
        yaml.dump(header, f)
        f.write("\n---\n\n")

        f.write(f'{metadata["description"]}\n\n')

        f.write("### Info\n")
        tbl_info = MarkdownTable(f, "Key", "Value")
        if "version" in metadata:
            tbl_info.write_row("Version", metadata["version"])
        if "app_version" in metadata:
            tbl_info.write_row("App version", metadata["app_version"])
        if task.image:
            tbl_info.write_row("Image", escaped(task.image))
        if "base_image" in metadata and task.image != metadata["base_image"]:
            tbl_info.write_row("Base image", escaped(metadata["base_image"]))
        if "maintainer" in metadata:
            tbl_info.write_row("Maintainer", metadata["maintainer"])
        if "info_url" in metadata:
            tbl_info.write_row("Info URL", metadata["info_url"])
        if "frequency" in metadata:
            tbl_info.write_row("Frequency", metadata["frequency"].name.title())

        f.write("\n")

        f.write("### Inputs\n")
        tbl_inputs = MarkdownTable(f, "Name", "Bids path", "Data type")
        for x in task.inputs:
            name, dtype, path = x
            tbl_inputs.write_row(escaped(name), escaped(path), escaped(dtype))
        f.write("\n")

        f.write("### Outputs\n")
        tbl_outputs = MarkdownTable(f, "Name", "Data type")
        for x in task.outputs:
            name, dtype, path = x
            tbl_outputs.write_row(escaped(name), escaped(dtype))
        f.write("\n")

        f.write("### Parameters\n")
        if not metadata.get("parameters", None):
            f.write("None\n")
        else:
            tbl_params = MarkdownTable(f, "Name", "Data type")
            for param in metadata["parameters"]:
                tbl_params.write_row("Todo", "Todo", "Todo")
        f.write("\n")


def main(args):
    sys.path.insert(0, BASE_DIR)

    output_dir = args[0]

    for dirpath, _, filenames in os.walk(os.path.join(BASE_DIR, "australianimagingservice")):
        for fn in filenames:
            if not fn.endswith(".py"):
                continue

            path = os.path.join(os.path.relpath(dirpath, BASE_DIR), fn)
            if is_bids_app(path):
                parse_bids_app(path, output_dir)


if __name__ == "__main__":
    main(sys.argv[1:])
