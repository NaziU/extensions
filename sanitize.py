import json
import os
import sys


INPUT_INDEX = "index.json"
BACKUP_INDEX = "index.bak.json"
REMOVED_INDEX = "index.removed.json"


TREAT_MIXED_AS_NSFW = (
    os.getenv(
        "TREAT_MIXED_AS_NSFW",
        "true",
    ).lower()
    in ("1", "true", "yes")
)


def load_index(path):
    with open(
        path,
        "r",
        encoding="utf-8",
    ) as f:
        return json.load(f)


def write_json(
    path,
    data,
    minified=False,
):
    with open(
        path,
        "w",
        encoding="utf-8",
    ) as f:

        if minified:
            json.dump(
                data,
                f,
                separators=(",", ":"),
                ensure_ascii=False,
            )

        else:
            json.dump(
                data,
                f,
                indent=2,
                ensure_ascii=False,
            )

            f.write("\n")


def find_extensions(data):

    if not isinstance(data, dict):
        return None, None

    extension_list = data.get(
        "extensionList"
    )

    if (
        isinstance(extension_list, dict)
        and isinstance(
            extension_list.get("extensions"),
            list,
        )
    ):
        return (
            extension_list,
            "extensions",
        )

    return None, None


def get_content_warning(extension):

    warning = (
        extension.get("contentWarning")
        or extension.get("content_warning")
        or ""
    )

    return str(warning).upper()


def is_forbidden(extension):

    warning = get_content_warning(
        extension
    )

    if (
        "CONTENT_WARNING_NSFW"
        in warning
    ):
        return True

    if (
        "CONTENT_WARNING_MIXED"
        in warning
    ):
        return TREAT_MIXED_AS_NSFW

    # Legacy field.
    nsfw = extension.get("nsfw")

    if nsfw in (
        1,
        True,
        "1",
        "true",
        "True",
    ):
        return True

    return False


def main():

    if not os.path.exists(
        INPUT_INDEX
    ):
        print(
            f"ERROR: {INPUT_INDEX} not found.",
            file=sys.stderr,
        )
        return 2

    print(
        "Loading upstream index..."
    )

    data = load_index(
        INPUT_INDEX
    )

    container, key = (
        find_extensions(data)
    )

    if container is None:
        print(
            "ERROR: Could not find "
            "extensionList.extensions "
            "in index.json.",
            file=sys.stderr,
        )
        return 3

    extensions = container[key]

    total = len(extensions)

    kept = []
    removed = []

    unspecified = []

    for extension in extensions:

        if not isinstance(
            extension,
            dict,
        ):
            print(
                "WARNING: Non-object "
                "extension encountered. "
                "Keeping it."
            )

            kept.append(extension)
            continue

        warning = get_content_warning(
            extension
        )

        if (
            "CONTENT_WARNING_UNSPECIFIED"
            in warning
            or not warning
        ):
            unspecified.append(
                extension.get(
                    "name",
                    "<unknown>",
                )
            )

        if is_forbidden(
            extension
        ):
            removed.append(
                extension
            )
        else:
            kept.append(
                extension
            )

    removed_count = len(
        removed
    )

    kept_count = len(
        kept
    )

    removed_ratio = (
        removed_count / total
        if total
        else 0
    )

    print("")
    print(
        "=============================="
    )
    print(
        "Sanitization results"
    )
    print(
        "=============================="
    )

    print(
        f"Total extensions : {total}"
    )

    print(
        f"Kept             : {kept_count}"
    )

    print(
        f"Removed          : {removed_count}"
    )

    print(
        f"Removed ratio    : "
        f"{removed_ratio:.2%}"
    )

    print(
        f"Unspecified      : "
        f"{len(unspecified)}"
    )

    # Safety mechanism:
    # Something went catastrophically wrong
    # if everything disappears.
    if (
        total > 0
        and kept_count == 0
    ):
        print(
            "ERROR: Sanitizer would "
            "remove every extension.",
            file=sys.stderr,
        )
        return 4

    # Another safety mechanism.
    # A sudden enormous deletion usually
    # means upstream changed its schema.
    if (
        total >= 20
        and removed_ratio > 0.80
    ):
        print(
            "ERROR: More than 80% of "
            "extensions would be removed.",
            file=sys.stderr,
        )
        return 5

    # Backup the upstream index
    # inside the temporary runner only.
    write_json(
        BACKUP_INDEX,
        data,
    )

    # Replace extension list.
    data[
        "extensionList"
    ][
        "extensions"
    ] = kept

    # Write sanitized protobuf-compatible JSON.
    write_json(
        INPUT_INDEX,
        data,
    )

    # Write removed list for debugging.
    write_json(
        REMOVED_INDEX,
        removed,
    )

    print("")
    print(
        "Removed extensions:"
    )

    for extension in removed[:20]:

        print(
            " -",
            extension.get(
                "name",
                "<unknown>",
            ),
            "|",
            extension.get(
                "packageName",
                "<unknown>",
            ),
            "|",
            extension.get(
                "contentWarning",
                "<unknown>",
            ),
        )

    if (
        removed_count > 20
    ):
        print(
            f" ... and "
            f"{removed_count - 20} more."
        )

    if unspecified:
        print("")
        print(
            "WARNING: "
            f"{len(unspecified)} "
            "extensions have "
            "UNSPECIFIED/unknown "
            "content warnings."
        )

        for name in unspecified[
            :20
        ]:
            print(
                " -",
                name,
            )

    print("")
    print(
        "Sanitizer completed "
        "successfully."
    )

    return 0


if __name__ == "__main__":
    sys.exit(
        main()
    )
