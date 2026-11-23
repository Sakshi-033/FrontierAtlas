
from pydantic import BaseModel, HttpUrl, Field
from typing import Optional, Any
from datetime import datetime
from enum import Enum


class Source(BaseModel):
    name: str = Field(min_length=1)
    url: HttpUrl


class StartupData(BaseModel):
    employeeCount: Optional[int] = Field(default=None, ge=0)

class StartupContent(BaseModel):
    entityName: str = Field(min_length=1)
    data: StartupData

class Startup(BaseModel):
    schemaVersion: str = "1.0"
    recordType: str = "STARTUP"
    source: Source
    content: StartupContent
    collectedAt: datetime


class DataRecord(BaseModel):
    schemaVersion: str = "1.0"
    recordType: str
    source: Source
    content: dict[str, Any]
    collectedAt: datetime


class PricingModel(str, Enum):
    FREE = "FREE"
    FREEMIUM = "FREEMIUM"
    PAID = "PAID"
    ENTERPRISE = "ENTERPRISE"

class ProductContent(BaseModel):
    productName: str = Field(min_length=1)
    startupName: Optional[str] = None
    productUrl: Optional[HttpUrl] = None
    pricingModel: Optional[PricingModel] = None

class Product(BaseModel):
    schemaVersion: str = "1.0"
    recordType: str = "PRODUCT"
    source: Source
    content: ProductContent
    collectedAt: datetime


class ResearchPaperContent(BaseModel):
    title: str = Field(min_length=1)
    authors: list[str] = Field(min_length=1)
    paper_url: HttpUrl
    github_url: Optional[HttpUrl] = None
    github_stars: Optional[int] = Field(default=None, ge=0)
    published_date: datetime

class ResearchPaper(BaseModel):
    schemaVersion: str = "1.0"
    recordType: str = "RESEARCH_PAPER"
    content: ResearchPaperContent

class JobContent(BaseModel):
    company: str = Field(min_length=1)
    date: datetime
    is_remote: bool
    role_family: str = Field(min_length=1)

class Job(BaseModel):
    schemaVersion: str = "1.0"
    recordType: str = "JOB"
    content: JobContent