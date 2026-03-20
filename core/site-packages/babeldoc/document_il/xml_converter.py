import copy
from pathlib import Path

import orjson
from xsdata.formats.dataclass.context import XmlContext
from xsdata.formats.dataclass.parsers import XmlParser
from xsdata.formats.dataclass.serializers import XmlSerializer
from xsdata.formats.dataclass.serializers.config import SerializerConfig

from babeldoc.document_il import il_version_1


class XMLConverter:
    def __init__(self):
        self.parser = XmlParser()
        config = SerializerConfig(indent="  ")
        context = XmlContext()
        self.serializer = XmlSerializer(context=context, config=config)

    def write_xml(self, document: il_version_1.Document, path: str):
        with Path(path).open("w", encoding="utf-8") as f:
            f.write(self.to_xml(document))

    def read_xml(self, path: str) -> il_version_1.Document:
        with Path(path).open(encoding="utf-8") as f:
            return self.from_xml(f.read())

    def to_xml(self, document: il_version_1.Document) -> str:
        return self.serializer.render(document)

    def from_xml(self, xml: str) -> il_version_1.Document:
        return self.parser.from_string(
            xml,
            il_version_1.Document,
        )

    def deepcopy(self, document: il_version_1.Document) -> il_version_1.Document:
        return copy.deepcopy(document)
        # return self.from_xml(self.to_xml(document))

    def to_json(self, document: il_version_1.Document) -> str:
        return orjson.dumps(
            document,
            option=orjson.OPT_APPEND_NEWLINE
            | orjson.OPT_INDENT_2
            | orjson.OPT_SORT_KEYS,
        ).decode()

    def write_json(self, document: il_version_1.Document, path: str):
        with Path(path).open("w", encoding="utf-8") as f:
            f.write(self.to_json(document))
