from dataclasses import dataclass
from pathlib import Path


GITHUB_URL_PREFIX = "https://github.com/"


def ref_path_name(ref: str) -> str:
    return ref.replace("/", "_")


def parse_repo_path_from_url(url: str) -> str | None:
    if not url.startswith(GITHUB_URL_PREFIX):
        return None
    return url.removeprefix(GITHUB_URL_PREFIX).removesuffix(".git")


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
        default_tag = "main"
        if link.startswith(GITHUB_URL_PREFIX):
            tokens = link.replace(GITHUB_URL_PREFIX, "").split(" ")

            if len(tokens) == 1:
                return GitHubLink(url=GITHUB_URL_PREFIX + tokens[0], tag=default_tag, subdir=versioned_repo_path(tokens[0], default_tag))

            if len(tokens) == 2:
                return GitHubLink(url=GITHUB_URL_PREFIX + tokens[0], tag=tokens[1], subdir=versioned_repo_path(tokens[0], tokens[1]))

        print(f"Unexpected github link. Format: {GITHUB_URL_PREFIX}your_repo tag. Tag is optional, {default_tag} is default")
        return None
