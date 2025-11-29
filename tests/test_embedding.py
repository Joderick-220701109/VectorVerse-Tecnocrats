"""
Tests for embedding service.
"""
import os
import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock

# Set TESTING flag before any imports
os.environ.setdefault("TESTING", "true")

from app.services.embedding import embed_text, embed_image_from_stream
from app.config import Config


class TestEmbedText:
    """Tests for text embedding functionality."""

    @patch('app.services.embedding.text_model')
    @patch('app.services.embedding.insert_chunk')
    def test_embed_text_basic(self, mock_insert_chunk, mock_text_model):
        """Test basic text embedding."""
        # Setup
        mock_conn = Mock()
        mock_text_model.encode.return_value = np.array([0.1] * Config.TEXT_EMBEDDING_DIM)
        mock_insert_chunk.return_value = 123

        # Execute
        result = embed_text(
            mock_conn,
            "test text",
            document_id=1,
            page_number=1,
            chunk_index=1,
        )

        # Assert
        assert result == 123
        mock_text_model.encode.assert_called_once_with("test text")
        mock_insert_chunk.assert_called_once()
        call_kwargs = mock_insert_chunk.call_args[1]
        assert call_kwargs['document_id'] == 1
        assert call_kwargs['page_number'] == 1
        assert call_kwargs['chunk_index'] == 1
        assert call_kwargs['content'] == "test text"
        assert len(call_kwargs['text_embedding']) == Config.TEXT_EMBEDDING_DIM

    @patch('app.services.embedding.text_model')
    def test_embed_text_dimension_mismatch(self, mock_text_model):
        """Test that dimension mismatch raises ValueError."""
        # Setup
        mock_conn = Mock()
        wrong_dim = Config.TEXT_EMBEDDING_DIM + 1
        mock_text_model.encode.return_value = np.array([0.1] * wrong_dim)

        # Execute & Assert
        with pytest.raises(ValueError, match="Text embedding dimension mismatch"):
            embed_text(
                mock_conn,
                "test text",
                document_id=1,
                page_number=1,
                chunk_index=1,
            )


class TestEmbedImageFromStream:
    """Tests for image embedding functionality."""

    @patch('app.services.embedding.clip_model')
    @patch('app.services.embedding.clip_processor')
    @patch('app.services.embedding.insert_chunk')
    @patch('app.services.embedding._decode_pdf_image_stream')
    def test_embed_image_from_stream_success(
        self, mock_decode, mock_insert_chunk, mock_processor, mock_model
    ):
        """Test successful image embedding."""
        # Setup
        from PIL import Image
        mock_conn = Mock()
        mock_img = Image.new('RGB', (100, 100), color='red')
        mock_decode.return_value = mock_img
        
        mock_processor.return_value = {'pixel_values': Mock()}
        mock_output = MagicMock()
        mock_output.__getitem__.return_value.cpu.return_value.numpy.return_value.tolist.return_value = [0.1] * Config.IMAGE_EMBEDDING_DIM
        mock_model.get_image_features.return_value = mock_output

        # Execute
        result = embed_image_from_stream(
            mock_conn,
            b'fake_image_data',
            "test_image.png",
            document_id=1,
            page_number=1,
            chunk_index=1,
            linked_chunk_id=None,
        )

        # Assert
        assert result is not None
        assert isinstance(result, str)  # base64 string
        mock_decode.assert_called_once()
        mock_insert_chunk.assert_called_once()

    @patch('app.services.embedding._decode_pdf_image_stream')
    def test_embed_image_from_stream_empty_data(self, mock_decode):
        """Test that empty stream data returns None."""
        # Setup
        mock_conn = Mock()
        mock_decode.return_value = None

        # Execute
        result = embed_image_from_stream(
            mock_conn,
            b'',
            "test_image.png",
            document_id=1,
            page_number=1,
            chunk_index=1,
            linked_chunk_id=None,
        )

        # Assert
        assert result is None

    @patch('app.services.embedding._decode_pdf_image_stream')
    def test_embed_image_from_stream_decode_failure(self, mock_decode):
        """Test that decode failure returns None."""
        # Setup
        mock_conn = Mock()
        mock_decode.return_value = None

        # Execute
        result = embed_image_from_stream(
            mock_conn,
            b'invalid_image_data',
            "test_image.png",
            document_id=1,
            page_number=1,
            chunk_index=1,
            linked_chunk_id=None,
        )

        # Assert
        assert result is None

