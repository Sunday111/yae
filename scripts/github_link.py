from dataclasses import dataclass
from pathlib import Path


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
                return GitHubLink(url=prefix + tokens[0], tag=default_tag, subdir=Path(tokens[0]))

            if len(tokens) == 2:
                return GitHubLink(url=prefix + tokens[0], tag=tokens[1], subdir=Path(tokens[0]))

        print(f"Unexpected github link. Format: {prefix}your_repo tag. Tag is optional, {default_tag} is default")
        return None
