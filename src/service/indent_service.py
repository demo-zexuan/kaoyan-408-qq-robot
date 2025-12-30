from pydantic import BaseModel, Field


class Intent(BaseModel):
    name: str = Field(default=..., description="意图名称")
    description: str = Field(default=..., description="意图描述")
