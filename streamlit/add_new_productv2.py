import json
import logging
import os
import uuid
from datetime import datetime
from io import BytesIO
from typing import Any, List, Optional, Tuple

import boto3
from dotenv import load_dotenv
from PIL import Image
from sqlalchemy import MetaData, create_engine, text
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import sessionmaker

import streamlit as st

# Load environment variables and configure logging
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
COLOR_OPTIONS = ["red", "blue", "green", "black", "white"]
TYPE_OPTIONS = ["T-shirt", "Hoodie", "Long Sleeve", "Other"]


class ProductManager:

    def __init__(self):
        """Initialize database connection configuration"""
        url = os.getenv("POSTGRES_PSYCOPG2_URL")

        if not url:
            raise ValueError(
                "Database connection URL not found in environment variables"
            )

        # Create SQLAlchemy engine with connection pool settings
        self.engine = create_engine(
            url,
            pool_pre_ping=True,  # Test connection before using
            pool_recycle=3600,  # Recycle connections after 1 hour
            echo=False,  # Set to True for SQL logging
        )
        self.Session = sessionmaker(bind=self.engine)
        self.metadata = MetaData()

        # Perform an initial connection test
        try:
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
                logger.info("Database connection successful")
        except OperationalError as e:
            logger.error(f"Database connection error: {e}")
            raise
        except ValueError as e:
            logger.error(f"Invalid connection URL: {e}")
            raise
        self.s3_client = boto3.client("s3")
        self.BUCKET_NAME = "products-rflkt-alpha"

    def sanitize_folder_name(self, title: str) -> str:
        """Sanitize the folder name by removing spaces and special characters."""
        # Replace multiple spaces with single hyphen and remove special characters
        sanitized = "-".join(title.lower().split())
        # Remove any remaining special characters except hyphens
        sanitized = "".join(c for c in sanitized if c.isalnum() or c == "-")
        return sanitized

    def upload_images_to_s3(
        self, images: List[BytesIO], product_title: str
    ) -> List[str]:
        """Upload images to S3 and return their URLs."""
        image_urls = []
        # Create a sanitized folder name using product title and uuid
        folder_name = (
            f"{self.sanitize_folder_name(product_title)}-{uuid.uuid4().hex[:8]}"
        )

        for idx, image in enumerate(images):
            try:
                key = f"{folder_name}/image_{idx}.jpg"
                self.s3_client.upload_fileobj(image, self.BUCKET_NAME, key)
                url = f"s3://{self.BUCKET_NAME}/{key}"
                image_urls.append(url)
            except Exception as e:
                st.error(f"Failed to upload image {idx}: {str(e)}")
        return image_urls

    def insert_product(self, product_data: dict, image_urls: List[str]) -> bool:
        """Insert product data into the database."""
        try:
            # Define the SQL insert statement
            insert_statement = text(
                """
                INSERT INTO products (title, description, color, in_stock, price, material, type, images)
                VALUES (:title, :description, :color, :in_stock, :price, :material, :type, :images)
            """
            )

            # Prepare the data to be inserted
            data = {
                "title": product_data["title"],
                "description": product_data["description"],
                "color": product_data["color"],
                "in_stock": product_data["in_stock"],
                "price": product_data["price"],
                "material": product_data["material"],
                "type": product_data["type"],
                "images": json.dumps(image_urls),
            }

            # Use a session to execute the insert statement
            with self.Session() as session:
                session.execute(insert_statement, data)
                session.commit()
                return True
        except SQLAlchemyError as e:
            st.error(f"Failed to insert product into database: {str(e)}")
            logger.error(f"SQLAlchemy error: {str(e)}")
            return False


# Rest of your Streamlit UI code remains the same
def init_session_state():
    """Initialize session state variables."""
    if "product" not in st.session_state:
        st.session_state.product = {
            "title": "",
            "description": "",
            "color": "red",
            "in_stock": True,
            "price": 0.0,
            "material": "",
            "type": "T-shirt",
            "images": [],
        }
    if "image_previews" not in st.session_state:
        st.session_state.image_previews = []


def handle_image_upload():
    """Handle image upload and preview."""
    uploaded_files = st.file_uploader(
        "Upload Product Images",
        accept_multiple_files=True,
        type=["png", "jpg", "jpeg"],
        key="image_uploader",
    )

    if uploaded_files:
        # Clear existing previews
        st.session_state.image_previews = []
        st.session_state.product["images"] = []

        # Create new image preview grid
        cols = st.columns(3)
        for idx, uploaded_file in enumerate(uploaded_files):
            # Convert to BytesIO for S3 upload
            image_bytes = BytesIO(uploaded_file.read())
            st.session_state.product["images"].append(image_bytes)

            # Reset file pointer for preview
            image_bytes.seek(0)

            # Create preview
            col_idx = idx % 3
            with cols[col_idx]:
                image = Image.open(image_bytes)
                st.image(image, caption=f"Image {idx + 1}")
                if st.button(f"Remove Image {idx + 1}", key=f"remove_{idx}"):
                    st.session_state.product["images"].pop(idx)
                    st.rerun()


def create_product_form(product_manager: ProductManager):
    """Create and display the product form."""
    st.subheader("Product Information")

    # Product Info Column 1
    col1, col2 = st.columns(2)

    with col1:
        # Title
        st.text_input(
            "Title",
            key="title",
            value=st.session_state.product["title"],
            help="Enter the product title",
            placeholder="Enter product title...",
        )

        # Description
        st.text_area(
            "Description",
            key="description",
            value=st.session_state.product["description"],
            help="Enter the product description",
            placeholder="Enter product description...",
            height=150,
        )

        # Material
        st.text_input(
            "Material",
            key="material",
            value=st.session_state.product["material"],
            help="Enter the product material",
            placeholder="Enter product material...",
        )

    with col2:
        # Color
        st.selectbox(
            "Color",
            options=COLOR_OPTIONS,
            key="color",
            index=COLOR_OPTIONS.index(st.session_state.product["color"]),
            help="Select product color",
        )

        # Type
        st.selectbox(
            "Type",
            options=TYPE_OPTIONS,
            key="type",
            index=TYPE_OPTIONS.index(st.session_state.product["type"]),
            help="Select product type",
        )

        # Price
        st.number_input(
            "Price",
            key="price",
            value=float(st.session_state.product["price"]),
            min_value=0.0,
            step=0.01,
            format="%.2f",
            help="Enter the product price",
        )

        # In Stock Switch
        st.toggle(
            "In Stock",
            key="in_stock",
            value=st.session_state.product["in_stock"],
            help="Toggle product availability",
        )


def main():
    st.title("Product Management System")

    try:
        # Initialize Product Manager
        product_manager = ProductManager()

        # Initialize session state
        init_session_state()

        # Create main container
        with st.container():
            # Product Information Form
            create_product_form(product_manager)

            st.markdown("---")

            # Image upload section
            st.subheader("Product Images")
            handle_image_upload()

            st.markdown("---")

            # Submit and Reset buttons
            col1, col2 = st.columns([1, 4])

            with col1:
                if st.button("Reset Form", type="secondary", use_container_width=True):
                    for key in st.session_state.product.keys():
                        if key == "in_stock":
                            st.session_state.product[key] = True
                        elif key == "price":
                            st.session_state.product[key] = 0.0
                        elif key == "color":
                            st.session_state.product[key] = "red"
                        elif key == "type":
                            st.session_state.product[key] = "T-shirt"
                        elif key == "images":
                            st.session_state.product[key] = []
                        else:
                            st.session_state.product[key] = ""
                    st.session_state.image_previews = []
                    st.rerun()

            with col2:
                if st.button(
                    "Create Product", type="primary", use_container_width=True
                ):
                    try:
                        product_data = {
                            key: st.session_state[key]
                            for key in [
                                "title",
                                "description",
                                "color",
                                "in_stock",
                                "price",
                                "material",
                                "type",
                            ]
                        }

                        # Validate required fields
                        if not product_data["title"]:
                            st.error("Please enter a product title")
                            return

                        if not st.session_state.product["images"]:
                            st.warning("Please upload at least one product image")
                            return

                        # Upload images using product title for folder name
                        image_urls = product_manager.upload_images_to_s3(
                            st.session_state.product["images"], product_data["title"]
                        )

                        if product_manager.insert_product(product_data, image_urls):
                            st.success("Product created successfully!")
                            # Clear session state after successful product creation
                            for key in st.session_state.product.keys():
                                if key == "in_stock":
                                    st.session_state.product[key] = True
                                elif key == "price":
                                    st.session_state.product[key] = 0.0
                                elif key == "color":
                                    st.session_state.product[key] = "red"
                                elif key == "type":
                                    st.session_state.product[key] = "T-shirt"
                                elif key == "images":
                                    st.session_state.product[key] = []
                                else:
                                    st.session_state.product[key] = ""

                            with st.expander("Product Preview", expanded=True):
                                st.json({**product_data, "image_urls": image_urls})
                        else:
                            st.error("Failed to create product in database")
                            # Log the full product data for debugging
                            logger.error(f"Product data: {product_data}")
                            logger.error(f"Image URLs: {image_urls}")

                    except Exception as e:
                        st.error(f"Error creating product: {str(e)}")

    except Exception as e:
        st.error(f"Application Error: {str(e)}")
        logger.error(f"Application Error: {str(e)}")


if __name__ == "__main__":
    main()
