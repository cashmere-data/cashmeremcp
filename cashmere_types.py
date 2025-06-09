from typing import TypedDict


# --- SearchPublicationsResponse ---
class SearchPublicationItem(TypedDict):
    block_uuid: str
    text_chunk: str
    distance: float
    section_label: str
    book_uuid: str
    book_title: str
    block_type: str
    buy_book_url: str
    embedding_id: int
    block_uuids: list[str]


SearchPublicationsResponse = list[SearchPublicationItem]


# --- PublicationsResponse ---
class PublicationData(TypedDict):
    title: str
    subtitle: str | None
    creators: list[str] | None
    creation_date: str | None
    publisher: str | None


class PublicationItem(TypedDict):
    uuid: str
    data: PublicationData
    cover_image: str | None


class PublicationsResponse(TypedDict):
    items: list[PublicationItem]
    count: int


# --- CollectionsResponse ---
class Collection(TypedDict):
    id: int
    name: str
    description: str | None
    owner_id: int
    created_at: str
    updated_at: str


class CollectionsResponse(TypedDict):
    items: list[Collection]
    count: int


# --- Publication ---
class NavItem(TypedDict):
    level: int
    label: str
    href: str | None
    full_href: str | None
    anchor: str | None
    order: int
    epub_item_id: str | None
    section_block_uuid: str | None
    cfi: str | None
    partition_type: str | None


class MetadataProperty(TypedDict, total=False):
    property1: str
    property2: str


class PublicationMetadata(TypedDict, total=False):
    property1: MetadataProperty
    property2: MetadataProperty


class PublicationDataFull(TypedDict):
    title: str
    subtitle: str | None
    cover_image: str | None
    creators: list[str] | None
    nav: list[NavItem]
    creation_date: str | None
    publisher: str | None
    epub_url: str | None
    file_url: str | None
    source_url: str | None
    metadata: PublicationMetadata | None


class Publication(TypedDict):
    uuid: str
    data: PublicationDataFull
    license_rights: list[str]
