from typing import List, Optional
from pydantic import BaseModel

class SubCategoryResponse(BaseModel):
    id: str
    slug: str
    name: str
    seo_title: Optional[str] = None
    seo_description: Optional[str] = None
    sort_order: int
    item_count: int

    class Config:
        from_attributes = True

class SectionResponse(BaseModel):
    id: str
    slug: str
    name: str
    description: Optional[str] = None
    icon_name: Optional[str] = None
    sort_order: int
    item_count: int
    categories: List[SubCategoryResponse]

    class Config:
        from_attributes = True

class TaxonomyResponse(BaseModel):
    sections: List[SectionResponse]
    total_assets: int

