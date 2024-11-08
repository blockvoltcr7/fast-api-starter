import json
import logging
import os
import uuid
from datetime import datetime
from io import BytesIO
from typing import Any, List, Optional, Tuple

import boto3
import pg8000.native
from dotenv import load_dotenv
from PIL import Image

import streamlit as st

# Load environment variables and configure logging
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
COLOR_OPTIONS = ["red", "blue", "green", "black", "white"]
TYPE_OPTIONS = ["T-shirt", "Hoodie", "Long Sleeve", "Other"]


class PostgresClient:
    """Utility class for PostgreSQL database operations using pg8000"""

    def __init__(self):
        """Initialize database connection configuration"""
        url = os.getenv("POSTGRES_URL")
        if not url:
            raise ValueError(
                "Database connection URL not found in environment variables"
            )

        # Parse connection URL
        url_parts = url.replace("postgres://", "").split("@")
        user_pass = url_parts[0].split(":")
        host_port_db = url_parts[1].split("/")
        host_port = host_port_db[0].split(":")

        self.config = {
            "user": user_pass[0],
            "password": user_pass[1],
            "host": host_port[0],
            "port": int(host_port[1]),
            "database": host_port_db[1].split("?")[0],
            "ssl_context": True,
        }
        self.conn = None

    def connect(self) -> Tuple[bool, Optional[str]]:
        """Establishes a connection to the PostgreSQL database."""
        try:
            self.conn = pg8000.native.Connection(**self.config)
            return True, None
        except Exception as e:
            error_msg = f"Error connecting to PostgreSQL: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def execute_query(self, query: str, params: dict = None) -> List[tuple]:
        """Execute a SQL query"""
        if not self.conn:
            success, error = self.connect()
            if not success:
                raise Exception(f"Failed to connect to database: {error}")

        try:
            # Use run method with named parameters
            return self.conn.run(query, params or {})
        except Exception as e:
            logger.error(f"Query execution error: {e}")
            raise

    def insert_record(
        self, table_name: str, columns: List[str], values: List[Any]
    ) -> bool:
        """Insert a new record into a table"""
        try:
            # Prepare the query with named placeholders
            columns_str = ", ".join(columns)
            placeholders = ", ".join([f":{col}" for col in columns])
            query = f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})"

            # Create a dictionary of parameters for pg8000 native binding
            params = {}
            for col, val in zip(columns, values):
                # Handle special cases for JSON serialization
                if isinstance(val, list):
                    # Convert list to JSON string if needed
                    params[col] = json.dumps(val)
                elif isinstance(val, bool):
                    # Ensure boolean is correctly handled
                    params[col] = val
                elif isinstance(val, (int, float, str)):
                    params[col] = val
                else:
                    # Convert other types to string
                    params[col] = str(val)

            # Execute the query with prepared parameters
            self.execute_query(query, params)
            logger.info(f"Record inserted into {table_name}")
            return True
        except Exception as e:
            logger.error(f"Error inserting record into {table_name}: {e}")
            return False


class ProductManager:
    def __init__(self):
        self.db = PostgresClient()
        self.s3_client = boto3.client("s3")

    def create_product_bucket(self, product_type: str) -> str:
        """Create an S3 bucket for a product type if it doesn't exist."""
        bucket_name = f"products-{product_type.lower()}-{uuid.uuid4().hex[:8]}"
        try:
            self.s3_client.create_bucket(Bucket=bucket_name)
            return bucket_name
        except Exception as e:
            st.error(f"Failed to create bucket: {str(e)}")
            return None

    def upload_images_to_s3(
        self, bucket_name: str, images: List[BytesIO], product_id: str
    ) -> List[str]:
        """Upload images to S3 and return their URLs."""
        image_urls = []
        for idx, image in enumerate(images):
            try:
                key = f"{product_id}/image_{idx}.jpg"
                self.s3_client.upload_fileobj(image, bucket_name, key)
                url = f"s3://{bucket_name}/{key}"
                image_urls.append(url)
            except Exception as e:
                st.error(f"Failed to upload image {idx}: {str(e)}")
        return image_urls

    def insert_product(self, product_data: dict, image_urls: List[str]) -> bool:
        """Insert product data into the database."""
        try:
            columns = [
                "title",
                "description",
                "color",
                "in_stock",
                "price",
                "material",
                "type",
                "images",
            ]
            values = [
                product_data["title"],
                product_data["description"],
                product_data["color"],
                product_data["in_stock"],
                product_data["price"],
                product_data["material"],
                product_data["type"],
                json.dumps(image_urls),
            ]

            return self.db.insert_record("products", columns, values)
        except Exception as e:
            st.error(f"Failed to insert product into database: {str(e)}")
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

                        bucket_name = product_manager.create_product_bucket(
                            product_data["type"]
                        )
                        if not bucket_name:
                            st.error("Failed to create storage bucket")
                            return

                        product_id = str(uuid.uuid4())
                        image_urls = product_manager.upload_images_to_s3(
                            bucket_name, st.session_state.product["images"], product_id
                        )

                        if product_manager.insert_product(product_data, image_urls):
                            st.success("Product created successfully!")
                            # Clear session state after successful product creation
                            for key in st.session_state.product.keys():
                                if key == 'in_stock':
                                    st.session_state.product[key] = True
                                elif key == 'price':
                                    st.session_state.product[key] = 0.0
                                elif key == 'color':
                                    st.session_state.product[key] = 'red'
                                elif key == 'type':
                                    st.session_state.product[key] = 'T-shirt'
                                elif key == 'images':
                                    st.session_state.product[key] = []
                                else:
                                    st.session_state.product[key] = ''
                            
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
