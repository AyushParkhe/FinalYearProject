class BaseSkillExtractor:
    def extract(self, title: str, metadata: dict | None = None) -> list[str]:
        """
        Base contract for all sources.

        metadata allows optional source-specific signals
        without breaking the interface.
        """
        raise NotImplementedError
