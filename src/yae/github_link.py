from dataclasses import dataclass
from pathlib import Path


def ref_path_name(ref: str) -> str:
    return ref.replace("/", "_")


def versioned_repo_path(repo_path: str, ref: str) -> Path:
    parts = Path(repo_path).parts
    if len(parts) >= 2:
        return Path(parts[0], ref_path_name(ref), *parts[1:])
    return Path(ref_path_name(ref), repo_path)


@dataclass
class GitHubLink:
    url: str
    tag: str
    subdir: Path

    @staticmethod
    def parse(link: str) -> "GitHubLink":
        prefix = "https://github.com/"
        default_tag = "main"
        if link.startswith(prefix):
            tokens = link.replace(prefix, "").split(" ")

            if len(tokens) == 1:
                return GitHubLink(url=prefix + tokens[0], tag=default_tag, subdir=versioned_repo_path(tokens[0], default_tag))

            if len(tokens) == 2:
                return GitHubLink(url=prefix + tokens[0], tag=tokens[1], subdir=versioned_repo_path(tokens[0], tokens[1]))

        print(f"Unexpected github link. Format: {prefix}your_repo tag. Tag is optional, {default_tag} is default")
        return None
