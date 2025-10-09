from pydantic import BaseModel


class SearchPublicationItem(BaseModel):
    embedding_id: str | int
    content: str
    view_source_url: str | None = None
    score: float | None = None
    distance: float | None = None
    omnipub_uuid: str | None = None
    omnipub_title: str | None = None
    section_label: str | None = None
    omnipub_publisher: str | None = None
    omnipub_cover_image: str | None = None


SearchPublicationsResponse = list[SearchPublicationItem]


class PublicationData(BaseModel):
    title: str
    subtitle: str | None = None
    creators: list[str] | None = None
    creation_date: str | None = None
    publisher: str | None = None


class PublicationItem(BaseModel):
    uuid: str
    data: PublicationData
    cover_image: str | None = None


class PublicationsResponse(BaseModel):
    items: list[PublicationItem]
    count: int


class Collection(BaseModel):
    id: int
    name: str
    description: str | None = None
    owner_id: int
    created_at: str
    updated_at: str
    pubs_count: int
    get_pubs_url: str


class CollectionsResponse(BaseModel):
    items: list[Collection]
    count: int


class NavItem(BaseModel):
    level: int
    order: int
    section_block_uuid: str
    label: str | None = None
    href: str
    full_href: str
    anchor: str | None = None
    epub_item_id: str | None = None
    cfi: str | None = None
    partition_type: str | None = None


class MetadataProperty(BaseModel):
    property1: str | None = None
    property2: str | None = None


class PublicationMetadata(BaseModel):
    property1: MetadataProperty | None = None
    property2: MetadataProperty | None = None


class PublicationDataFull(BaseModel):
    title: str
    subtitle: str | None = None
    cover_image: str | None = None
    creators: list[str] | None = None
    nav: list[NavItem] | None = None
    creation_date: str | None = None
    publisher: str | None = None
    epub_url: str | None = None
    file_url: str | None = None
    source_url: str | None = None
    metadata: PublicationMetadata | None = None


class Publication(BaseModel):
    uuid: str
    data: PublicationDataFull
    license_rights: list[str] | None = None


class APIResponseError(ValueError):
    """Encountered unexpected response format."""
    pass
