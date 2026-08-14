from auth import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_verify_password_accepts_correct_password() -> None:
    # Arrange
    password = "some_random_password_nestor"
    hashed = hash_password(password)

    # Act
    result = verify_password(password, hashed)

    # Assert
    assert result is True


def test_verify_password_rejects_wrong_password() -> None:
    # Arrange
    hashed = hash_password("some_random_password_nestor")

    # Act
    result = verify_password("a_different_password", hashed)

    # Assert
    assert result is False


def test_hash_password_uses_a_random_salt() -> None:
    # Arrange
    password = "some_random_password_nestor"

    # Act
    first = hash_password(password)
    second = hash_password(password)

    # Assert
    assert first != second


def test_hash_password_does_not_contain_plaintext() -> None:
    # Arrange
    password = "some_random_password_nestor"

    # Act
    hashed = hash_password(password)

    # Assert
    assert password not in hashed


def test_decode_access_token_returns_user_id() -> None:
    # Arrange
    token = create_access_token(42)

    # Act
    result = decode_access_token(token)

    # Assert
    assert result == 42


def test_decode_access_token_rejects_malformed_token() -> None:
    # Act
    result = decode_access_token("not-a-real-token")

    # Assert
    assert result is None


def test_decode_access_token_rejects_tampered_token() -> None:
    # Arrange
    token = create_access_token(42)
    tampered = token[:-4] + "AAAA"

    # Act
    result = decode_access_token(tampered)

    # Assert
    assert result is None
