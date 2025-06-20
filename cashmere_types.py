from typing import TypedDict


# --- SearchPublicationsResponse ---
class SearchPublicationItem(TypedDict):
    embedding_id: int
    content: str
    view_source_url: str
    distance: float
    omnipub_uuid: str
    omnipub_title: str
    section_label: str
    omnipub_publisher: str
    omnipub_cover_image: str


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
    pubs_count: int
    get_pubs_url: str


class CollectionsResponse(TypedDict):
    items: list[Collection]
    count: int


# --- Publication ---
class NavItem(TypedDict, total=False):
    level: int
    label: str
    href: str
    full_href: str
    anchor: str
    order: int
    epub_item_id: str
    section_block_uuid: str
    cfi: str
    partition_type: str


class MetadataProperty(TypedDict, total=False):
    property1: str
    property2: str


class PublicationMetadata(TypedDict, total=False):
    property1: MetadataProperty
    property2: MetadataProperty


class PublicationDataFull(TypedDict, total=False):
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


class Publication(TypedDict, total=False):
    uuid: str
    data: PublicationDataFull
    license_rights: list[str]
