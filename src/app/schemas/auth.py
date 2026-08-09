from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class UserCreate(BaseModel):
    login: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=3, max_length=50)
    repeat_password: str

    @model_validator(mode="after")
    def password_match(self) -> "UserCreate":
        if self.password != self.repeat_password:
            raise ValueError("Passwords don't match")
        return self


class UserLogin(BaseModel):
    login: str
    password: str


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    login: str
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
