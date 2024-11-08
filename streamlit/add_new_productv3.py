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
CATEGORY_OPTIONS = ["Men", "Women", "Unisex", "Kids", "Accessories"]
STATUS_OPTIONS = ["active", "draft", "inactive", "archived"]
CURRENCY_OPTIONS = ["USD", "EUR", "GBP", "CAD", "AUD"]


def generate_sku(title: str, category: str, color: str, type: str) -> str:
    """Generate a unique SKU based on product attributes."""
    # Get first 3 letters of each attribute (uppercase)
    title_code = "".join(c for c in title[:3] if c.isalnum()).upper()
    category_code = "".join(c for c in category[:2] if c.isalnum()).upper()
    color_code = "".join(c for c in color[:2] if c.isalnum()).upper()
    type_code = "".join(c for c in type[:2] if c.isalnum()).upper()

    # Generate timestamp-based unique identifier
    unique_id = datetime.now().strftime("%y%m%d%H%M")

    # Combine all parts
    sku = f"{category_code}{type_code}{color_code}{title_code}-{unique_id}"

    return sku


class ProductManager:
    def __init__(self):
        """Initialize database connection configuration"""
        url = os.getenv("POSTGRES_PSYCOPG2_URL")

        if not url:
            raise ValueError(
                "Database connection URL not found in environment variables"
            )

        self.engine = create_engine(
            url,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=False,
        )
        self.Session = sessionmaker(bind=self.engine)
        self.metadata = MetaData()

        try:
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
                logger.info("Database connection successful")
        except OperationalError as e:
            logger.error(f"Database connection error: {e}")
            raise

        self.s3_client = boto3.client("s3")
        self.BUCKET_NAME = "products-rflkt-alpha"

    def sanitize_folder_name(self, title: str) -> str:
        """Sanitize the folder name by removing spaces and special characters."""
        sanitized = "-".join(title.lower().split())
        sanitized = "".join(c for c in sanitized if c.isalnum() or c == "-")
        return sanitized

    def upload_images_to_s3(
        self, images: List[BytesIO], product_title: str
    ) -> Tuple[str, List[str]]:
        """Upload images to S3 and return thumbnail URL and additional image URLs."""
        image_urls = []
        folder_name = (
            f"{self.sanitize_folder_name(product_title)}-{uuid.uuid4().hex[:8]}"
        )

        thumbnail_url = None
        for idx, image in enumerate(images):
            try:
                key = f"{folder_name}/image_{idx}.jpg"
                self.s3_client.upload_fileobj(image, self.BUCKET_NAME, key)
                url = f"s3://{self.BUCKET_NAME}/{key}"

                if idx == 0:  # First image is thumbnail
                    thumbnail_url = url
                else:
                    image_urls.append(url)
            except Exception as e:
                st.error(f"Failed to upload image {idx}: {str(e)}")

        return thumbnail_url, image_urls

    def insert_product(
        self, product_data: dict, thumbnail_url: str, additional_image_urls: List[str]
    ) -> bool:
        """Insert product data into the database."""
        try:
            insert_statement = text(
                """
                INSERT INTO products (
                    title, description, description_long, category, color, in_stock,
                    price, price_currency, material, type, sku, quantity_in_stock,
                    status, thumbnail_image, additional_images
                )
                VALUES (
                    :title, :description, :description_long, :category, :color, :in_stock,
                    :price, :price_currency, :material, :type, :sku, :quantity_in_stock,
                    :status, :thumbnail_image, :additional_images
                )
            """
            )

            sku = generate_sku(
                product_data["title"],
                product_data["category"],
                product_data["color"],
                product_data["type"],
            )

            data = {
                **product_data,
                "sku": sku,
                "thumbnail_image": thumbnail_url,
                "additional_images": json.dumps(additional_image_urls),
            }

            with self.Session() as session:
                session.execute(insert_statement, data)
                session.commit()
                return True
        except SQLAlchemyError as e:
            st.error(f"Failed to insert product into database: {str(e)}")
            logger.error(f"SQLAlchemy error: {str(e)}")
            return False


def init_session_state():
    """Initialize session state variables."""
    if "product" not in st.session_state:
        st.session_state.product = {
            "title": "",
            "description": "",
            "description_long": "",
            "category": "Unisex",
            "color": "red",
            "in_stock": True,
            "price": 0.0,
            "price_currency": "USD",
            "material": "",
            "type": "T-shirt",
            "quantity_in_stock": 0,
            "status": "active",
            "images": [],
        }
    if "image_previews" not in st.session_state:
        st.session_state.image_previews = []


def handle_image_upload():
    """Handle image upload and preview."""
    uploaded_files = st.file_uploader(
        "Upload Product Images (First image will be the thumbnail)",
        accept_multiple_files=True,
        type=["png", "jpg", "jpeg"],
        key="image_uploader",
        help="The first image uploaded will be used as the product thumbnail",
    )

    if uploaded_files:
        st.session_state.image_previews = []
        st.session_state.product["images"] = []

        cols = st.columns(3)
        for idx, uploaded_file in enumerate(uploaded_files):
            image_bytes = BytesIO(uploaded_file.read())
            st.session_state.product["images"].append(image_bytes)

            image_bytes.seek(0)
            col_idx = idx % 3
            with cols[col_idx]:
                image = Image.open(image_bytes)
                caption = "Thumbnail" if idx == 0 else f"Image {idx + 1}"
                st.image(image, caption=caption)
                if st.button(f"Remove Image {idx + 1}", key=f"remove_{idx}"):
                    st.session_state.product["images"].pop(idx)
                    st.rerun()


def create_product_form(product_manager: ProductManager):
    """Create and display the product form."""
    st.subheader("Product Information")

    col1, col2 = st.columns(2)

    with col1:
        st.text_input(
            "Title",
            key="title",
            value=st.session_state.product["title"],
            help="Enter the product title",
            placeholder="Enter product title...",
        )

        st.text_area(
            "Short Description",
            key="description",
            value=st.session_state.product["description"],
            help="Enter a brief product description",
            placeholder="Enter short description...",
            height=100,
        )

        st.text_area(
            "Long Description",
            key="description_long",
            value=st.session_state.product["description_long"],
            help="Enter a detailed product description",
            placeholder="Enter detailed description...",
            height=200,
        )

        st.text_input(
            "Material",
            key="material",
            value=st.session_state.product["material"],
            help="Enter the product material",
            placeholder="Enter product material...",
        )

    with col2:
        st.selectbox(
            "Category",
            options=CATEGORY_OPTIONS,
            key="category",
            index=CATEGORY_OPTIONS.index(st.session_state.product["category"]),
            help="Select product category",
        )

        st.selectbox(
            "Color",
            options=COLOR_OPTIONS,
            key="color",
            index=COLOR_OPTIONS.index(st.session_state.product["color"]),
            help="Select product color",
        )

        st.selectbox(
            "Type",
            options=TYPE_OPTIONS,
            key="type",
            index=TYPE_OPTIONS.index(st.session_state.product["type"]),
            help="Select product type",
        )

        col2_1, col2_2 = st.columns(2)
        with col2_1:
            st.number_input(
                "Price",
                key="price",
                value=float(st.session_state.product["price"]),
                min_value=0.0,
                step=0.01,
                format="%.2f",
                help="Enter the product price",
            )

            st.number_input(
                "Quantity in Stock",
                key="quantity_in_stock",
                value=int(st.session_state.product["quantity_in_stock"]),
                min_value=0,
                step=1,
                help="Enter the quantity in stock",
            )

        with col2_2:
            st.selectbox(
                "Currency",
                options=CURRENCY_OPTIONS,
                key="price_currency",
                index=CURRENCY_OPTIONS.index(
                    st.session_state.product["price_currency"]
                ),
                help="Select price currency",
            )

            st.selectbox(
                "Status",
                options=STATUS_OPTIONS,
                key="status",
                index=STATUS_OPTIONS.index(st.session_state.product["status"]),
                help="Select product status",
            )

        st.toggle(
            "In Stock",
            key="in_stock",
            value=st.session_state.product["in_stock"],
            help="Toggle product availability",
        )


def main():
    st.title("Product Management System")

    try:
        product_manager = ProductManager()
        init_session_state()

        with st.container():
            create_product_form(product_manager)
            st.markdown("---")

            st.subheader("Product Images")
            handle_image_upload()
            st.markdown("---")

            col1, col2 = st.columns([1, 4])

            with col1:
                if st.button("Reset Form", type="secondary", use_container_width=True):
                    for key in st.session_state.product.keys():
                        if key == "in_stock":
                            st.session_state.product[key] = True
                        elif key == "price":
                            st.session_state.product[key] = 0.0
                        elif key == "quantity_in_stock":
                            st.session_state.product[key] = 0
                        elif key == "color":
                            st.session_state.product[key] = "red"
                        elif key == "type":
                            st.session_state.product[key] = "T-shirt"
                        elif key == "category":
                            st.session_state.product[key] = "Unisex"
                        elif key == "status":
                            st.session_state.product[key] = "active"
                        elif key == "price_currency":
                            st.session_state.product[key] = "USD"
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
                                "description_long",
                                "category",
                                "color",
                                "in_stock",
                                "price",
                                "price_currency",
                                "material",
                                "type",
                                "quantity_in_stock",
                                "status",
                            ]
                        }

                        if not product_data["title"]:
                            st.error("Please enter a product title")
                            return

                        if not st.session_state.product["images"]:
                            st.warning("Please upload at least one product image")
                            return

                        thumbnail_url, additional_image_urls = (
                            product_manager.upload_images_to_s3(
                                st.session_state.product["images"],
                                product_data["title"],
                            )
                        )

                        if product_manager.insert_product(
                            product_data, thumbnail_url, additional_image_urls
                        ):
                            st.success("Product created successfully!")

                            # Generate and display SKU
                            sku = generate_sku(
                                product_data["title"],
                                product_data["category"],
                                product_data["color"],
                                product_data["type"],
                            )
                            st.info(f"Generated SKU: {sku}")

                            with st.expander("Product Preview", expanded=True):
                                preview_data = {
                                    **product_data,
                                    "sku": sku,
                                    "thumbnail_image": thumbnail_url,
                                    "additional_images": additional_image_urls,
                                }
                                st.json(preview_data)

                            # Reset form
                            for key in st.session_state.product.keys():
                                if key == "in_stock":
                                    st.session_state.product[key] = True
                                elif key == "price":
                                    st.session_state.product[key] = 0.0
                                elif key == "quantity_in_stock":
                                    st.session_state.product[key] = 0
                                elif key == "color":
                                    st.session_state.product[key] = "red"
                                elif key == "type":
                                    st.session_state.product[key] = "T-shirt"
                                elif key == "category":
                                    st.session_state.product[key] = "Unisex"
                                elif key == "status":
                                    st.session_state.product[key] = "active"
                                elif key == "price_currency":
                                    st.session_state.product[key] = "USD"
                                elif key == "images":
                                    st.session_state.product[key] = []
                                else:
                                    st.session_state.product[key] = ""
                        else:
                            st.error("Failed to create product in database")
                            # Log the full product data for debugging
                            logger.error(f"Product data: {product_data}")
                            logger.error(f"Thumbnail URL: {thumbnail_url}")
                            logger.error(
                                f"Additional image URLs: {additional_image_urls}"
                            )

                    except Exception as e:
                        st.error(f"Error creating product: {str(e)}")
                        logger.error(f"Error creating product: {str(e)}")

    except Exception as e:
        st.error(f"Application Error: {str(e)}")
        logger.error(f"Application Error: {str(e)}")


if __name__ == "__main__":
    main()
