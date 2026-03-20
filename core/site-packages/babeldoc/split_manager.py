import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SplitPoint:
    """Represents a point where the document should be split"""

    start_page: int
    end_page: int
    estimated_complexity: float = 1.0
    chapter_title: str | None = None


class BaseSplitStrategy:
    """Base class for split strategies"""

    def determine_split_points(self, config) -> list[SplitPoint]:
        raise NotImplementedError


class PageCountStrategy(BaseSplitStrategy):
    """Split document based on page count"""

    def __init__(self, max_pages_per_part: int = 20):
        self.max_pages_per_part = max_pages_per_part

    def determine_split_points(self, config) -> list[SplitPoint]:
        from pymupdf import Document

        doc = Document(str(config.input_file))
        total_pages = doc.page_count

        split_points = []
        current_page = 0

        while current_page < total_pages:
            end_page = min(current_page + self.max_pages_per_part, total_pages)
            split_points.append(
                SplitPoint(
                    start_page=current_page,
                    end_page=end_page - 1,  # end_page is inclusive
                )
            )
            current_page = end_page

        return split_points


class SplitManager:
    """Manages document splitting process"""

    def __init__(self, config=None):
        self.strategy = config.split_strategy

    def determine_split_points(self, config) -> list[SplitPoint]:
        """Determine where to split the document"""
        return self.strategy.determine_split_points(config)

    def estimate_part_complexity(self, split_point: SplitPoint) -> float:
        """Estimate the complexity of a document part"""
        # Simple estimation based on page count for now
        return (
            split_point.end_page - split_point.start_page + 1
        ) * split_point.estimated_complexity
