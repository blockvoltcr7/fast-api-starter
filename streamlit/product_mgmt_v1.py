import json
import logging
import os
import uuid
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

import boto3
import requests
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

# Constants for Product Management
COLOR_OPTIONS = ["red", "blue", "green", "black", "white"]
TYPE_OPTIONS = ["T-shirt", "Hoodie", "Long Sleeve", "Other"]
CATEGORY_OPTIONS = ["Men", "Women", "Unisex", "Kids", "Accessories"]
STATUS_OPTIONS = ["active", "draft", "inactive", "archived"]
CURRENCY_OPTIONS = ["USD", "EUR", "GBP", "CAD", "AUD"]

# API Configuration
API_BASE_URL = "http://127.0.0.1:8000"

# Page Configuration
st.set_page_config(
    page_title="Management Portal",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)


# Initialize session state
def init_session_state():
    if "token" not in st.session_state:
        st.session_state.token = None
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "current_page" not in st.session_state:
        st.session_state.current_page = "Product Management"
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
            "thumbnail": None,
            "main_image": None,
            "additional_images": [],
        }
    if "image_previews" not in st.session_state:
        st.session_state.image_previews = []
    if "product_creation_result" not in st.session_state:
        st.session_state.product_creation_result = None
    if "last_created_sku" not in st.session_state:
        st.session_state.last_created_sku = None
    if "last_created_preview" not in st.session_state:
        st.session_state.last_created_preview = None


# Authentication Functions
def login_user(username: str, password: str) -> bool:
    try:
        response = requests.post(
            f"{API_BASE_URL}/token", data={"username": username, "password": password}
        )
        if response.status_code == 200:
            token_data = response.json()
            st.session_state.token = token_data["access_token"]
            st.session_state.authenticated = True
            return True
        return False
    except requests.RequestException as e:
        st.error(f"Login failed: {str(e)}")
        return False


def get_auth_headers() -> Dict[str, str]:
    if st.session_state.token:
        return {"Authorization": f"Bearer {st.session_state.token}"}
    return {}


def make_api_request(
    endpoint: str, method: str = "GET", params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    if not st.session_state.authenticated:
        st.error("Please log in first")
        return {}

    url = f"{API_BASE_URL}{endpoint}"
    headers = get_auth_headers()

    try:
        with st.spinner("Processing request..."):
            if method == "GET":
                response = requests.get(url, params=params, headers=headers)
            elif method == "POST":
                response = requests.post(url, params=params, headers=headers)

            if response.status_code == 401:
                st.session_state.authenticated = False
                st.session_state.token = None
                st.error("Session expired. Please log in again.")
                return {}

            response.raise_for_status()
            return response.json()
    except requests.RequestException as e:
        st.error(f"API Error: {str(e)}")
        return {}


# Login Form
def login_form():
    st.title("Login")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")

        if submit:
            if login_user(username, password):
                st.success("Successfully logged in!")
                st.rerun()
            else:
                st.error("Invalid credentials")


# Product Management Functions
class ProductManager:
    def __init__(self):
        """Initialize database connection configuration"""
        url = os.getenv("POSTGRES_PSYCOPG2_URL")
        if not url:
            raise ValueError("Database connection URL not found")

        self.engine = create_engine(url, pool_pre_ping=True, pool_recycle=3600)
        self.Session = sessionmaker(bind=self.engine)
        self.metadata = MetaData()

        # Test connection
        try:
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
                logger.info("Database connection successful")
        except OperationalError as e:
            logger.error(f"Database connection error: {e}")
            raise

        self.s3_client = boto3.client("s3")
        self.BUCKET_NAME = os.getenv("PRODUCT_BUCKET_NAME", "products-rflkt-alpha")

    def sanitize_folder_name(self, title: str) -> str:
        sanitized = "-".join(title.lower().split())
        sanitized = "".join(c for c in sanitized if c.isalnum() or c == "-")
        return sanitized

    def process_and_upload_image(
        self, image_file: BytesIO, bucket: str, key: str
    ) -> str:
        """
        Process and upload an image to S3, ensuring proper format and buffer handling.

        Args:
            image_file: BytesIO object containing the image
            bucket: S3 bucket name
            key: S3 object key (path)

        Returns:
            str: The public URL of the uploaded image
        """
        try:
            # Reset buffer position
            image_file.seek(0)

            # Convert image to PIL Image
            image = Image.open(image_file)

            # Ensure image is in RGBA mode to handle transparency
            if image.mode != "RGBA":
                image = image.convert("RGBA")

            # Create a new BytesIO object for the processed image
            processed_image = BytesIO()

            # Save as PNG to preserve transparency
            image.save(processed_image, format="PNG", optimize=True)

            # Reset buffer position after saving
            processed_image.seek(0)

            # Upload to S3 with appropriate content type
            self.s3_client.upload_fileobj(
                processed_image, bucket, key, ExtraArgs={"ContentType": "image/png"}
            )

            # Get the region
            region = os.getenv("AWS_REGION", "us-east-1")

            # Return the public URL
            return f"https://{bucket}.s3.{region}.amazonaws.com/{key}"

        except Exception as e:
            logger.error(f"Error processing and uploading image: {str(e)}")
            raise

    def upload_images_to_s3(
        self,
        thumbnail: BytesIO,
        main_image: BytesIO,
        additional_images: List[BytesIO],
        product_title: str,
    ) -> Tuple[str, str, List[str], str]:
        """
        Upload product images to S3 with proper image processing.

        Args:
            thumbnail: BytesIO object containing the thumbnail image
            main_image: BytesIO object containing the main image
            additional_images: List of BytesIO objects containing additional images
            product_title: Title of the product

        Returns:
            Tuple containing URLs for thumbnail, main image, additional images, and unique ID
        """
        image_urls = []
        unique_id = uuid.uuid4().hex[:8]
        folder_name = f"{self.sanitize_folder_name(product_title)}-{unique_id}"

        # Upload thumbnail
        thumbnail_url = None
        if thumbnail:
            try:
                thumbnail_name = f"{self.sanitize_folder_name(product_title)}_{unique_id}_thumbnail.png"
                key = f"{folder_name}/{thumbnail_name}"
                thumbnail_url = self.process_and_upload_image(
                    thumbnail, self.BUCKET_NAME, key
                )
            except Exception as e:
                logger.error(f"Failed to upload thumbnail: {str(e)}")
                st.error(f"Failed to upload thumbnail: {str(e)}")
                return None, None, [], unique_id

        # Upload main image
        main_image_url = None
        if main_image:
            try:
                main_image_name = (
                    f"{self.sanitize_folder_name(product_title)}_{unique_id}_main.png"
                )
                key = f"{folder_name}/{main_image_name}"
                main_image_url = self.process_and_upload_image(
                    main_image, self.BUCKET_NAME, key
                )
            except Exception as e:
                logger.error(f"Failed to upload main image: {str(e)}")
                st.error(f"Failed to upload main image: {str(e)}")
                return thumbnail_url, None, [], unique_id

        # Upload additional images
        for idx, image in enumerate(additional_images):
            try:
                image_name = f"{self.sanitize_folder_name(product_title)}_{unique_id}_additional_image_{idx + 1}.png"
                key = f"{folder_name}/{image_name}"
                url = self.process_and_upload_image(image, self.BUCKET_NAME, key)
                image_urls.append(url)
            except Exception as e:
                logger.error(f"Failed to upload additional image {idx + 1}: {str(e)}")
                st.error(f"Failed to upload additional image {idx + 1}: {str(e)}")

        return thumbnail_url, main_image_url, image_urls, unique_id

    def insert_product(
        self,
        product_data: dict,
        thumbnail_url: str,
        main_image_url: str,
        additional_image_urls: List[str],
        unique_id: str,
    ) -> bool:
        try:
            insert_statement = text(
                """
                INSERT INTO products (
                    title, description, description_long, category, color, in_stock,
                    price, price_currency, material, type, sku, quantity_in_stock,
                    status, thumbnail_image, main_image, additional_images, unique_id
                )
                VALUES (
                    :title, :description, :description_long, :category, :color, :in_stock,
                    :price, :price_currency, :material, :type, :sku, :quantity_in_stock,
                    :status, :thumbnail_image, :main_image, :additional_images, :unique_id
                )
            """
            )

            sku = self.generate_sku(
                product_data["title"],
                product_data["category"],
                product_data["color"],
                product_data["type"],
            )

            data = {
                **product_data,
                "sku": sku,
                "thumbnail_image": thumbnail_url,
                "main_image": main_image_url,
                "additional_images": json.dumps(additional_image_urls),
                "unique_id": unique_id,
            }

            with self.Session() as session:
                session.execute(insert_statement, data)
                session.commit()
                return True
        except SQLAlchemyError as e:
            st.error(f"Failed to insert product: {str(e)}")
            logger.error(f"SQLAlchemy error: {str(e)}")
            return False

    @staticmethod
    def generate_sku(title: str, category: str, color: str, type: str) -> str:
        title_code = "".join(c for c in title[:3] if c.isalnum()).upper()
        category_code = "".join(c for c in category[:2] if c.isalnum()).upper()
        color_code = "".join(c for c in color[:2] if c.isalnum()).upper()
        type_code = "".join(c for c in type[:2] if c.isalnum()).upper()
        unique_id = datetime.now().strftime("%y%m%d%H%M")
        return f"{category_code}{type_code}{color_code}{title_code}-{unique_id}"

    def delete_product(self, folder_name: str) -> Tuple[bool, str]:
        """
        Delete a product and its folder from both database and S3.
        folder_name format example: 'strength-and-honor-7a5671cb'
        Returns a tuple of (success: bool, message: str)
        """
        try:
            # First, get the product details using the unique_id from folder name
            unique_id = folder_name.split("-")[
                -1
            ]  # Get the last part after the last dash

            with self.Session() as session:
                # Delete from database using unique_id
                delete_stmt = text("DELETE FROM products WHERE unique_id = :unique_id")
                result = session.execute(delete_stmt, {"unique_id": unique_id})
                session.commit()

                if result.rowcount == 0:
                    return (
                        False,
                        f"Product with folder name {folder_name} not found in database",
                    )

                # Delete folder from S3
                try:
                    # List all objects in the folder
                    paginator = self.s3_client.get_paginator("list_objects_v2")
                    pages = paginator.paginate(
                        Bucket=self.BUCKET_NAME, Prefix=f"{folder_name}/"
                    )

                    delete_keys = []
                    for page in pages:
                        if "Contents" in page:
                            for obj in page["Contents"]:
                                delete_keys.append({"Key": obj["Key"]})

                    if delete_keys:
                        self.s3_client.delete_objects(
                            Bucket=self.BUCKET_NAME, Delete={"Objects": delete_keys}
                        )

                    return True, f"Product folder {folder_name} deleted successfully"

                except Exception as e:
                    logger.error(f"Error deleting S3 folder: {str(e)}")
                    return (
                        True,
                        f"Product deleted from database, but S3 folder deletion failed: {str(e)}",
                    )

        except SQLAlchemyError as e:
            logger.error(f"Database error while deleting product: {str(e)}")
            return False, f"Database error: {str(e)}"
        except Exception as e:
            logger.error(f"Error deleting product: {str(e)}")
            return False, f"Error: {str(e)}"


# Product Management UI
def create_product_form(product_manager: ProductManager):
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
        )

        st.selectbox(
            "Color",
            options=COLOR_OPTIONS,
            key="color",
            index=COLOR_OPTIONS.index(st.session_state.product["color"]),
        )

        st.selectbox(
            "Type",
            options=TYPE_OPTIONS,
            key="type",
            index=TYPE_OPTIONS.index(st.session_state.product["type"]),
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
            )

            st.number_input(
                "Quantity in Stock",
                key="quantity_in_stock",
                value=int(st.session_state.product["quantity_in_stock"]),
                min_value=0,
                step=1,
            )

        with col2_2:
            st.selectbox(
                "Currency",
                options=CURRENCY_OPTIONS,
                key="price_currency",
                index=CURRENCY_OPTIONS.index(
                    st.session_state.product["price_currency"]
                ),
            )

            st.selectbox(
                "Status",
                options=STATUS_OPTIONS,
                key="status",
                index=STATUS_OPTIONS.index(st.session_state.product["status"]),
            )

        st.toggle(
            "In Stock", key="in_stock", value=st.session_state.product["in_stock"]
        )


def handle_image_upload():
    # Thumbnail Image Upload
    st.subheader("Thumbnail Image")
    st.caption(
        "This image will be used as a small preview (recommended size: 150x150px)"
    )
    thumbnail_file = st.file_uploader(
        "Upload Thumbnail Image",
        type=["png", "jpg", "jpeg"],
        key="thumbnail_uploader",
    )

    # Display thumbnail preview
    if thumbnail_file:
        thumbnail_bytes = BytesIO(thumbnail_file.read())
        st.session_state.product["thumbnail"] = thumbnail_bytes

        thumbnail_bytes.seek(0)
        st.image(Image.open(thumbnail_bytes), caption="Thumbnail Preview", width=150)
        if st.button("Remove Thumbnail"):
            st.session_state.product["thumbnail"] = None
            st.rerun()

    st.markdown("---")

    # Main Image Upload
    st.subheader("Main Product Image")
    st.caption(
        "This image will be the primary product image (recommended size: 800x800px)"
    )
    main_image_file = st.file_uploader(
        "Upload Main Product Image",
        type=["png", "jpg", "jpeg"],
        key="main_image_uploader",
    )

    # Display main image preview
    if main_image_file:
        main_image_bytes = BytesIO(main_image_file.read())
        st.session_state.product["main_image"] = main_image_bytes

        main_image_bytes.seek(0)
        st.image(Image.open(main_image_bytes), caption="Main Image Preview", width=400)
        if st.button("Remove Main Image"):
            st.session_state.product["main_image"] = None
            st.rerun()

    st.markdown("---")

    # Additional Images Upload
    st.subheader("Additional Images")
    st.caption("Upload additional product images to show different angles or details")
    additional_files = st.file_uploader(
        "Upload Additional Product Images",
        accept_multiple_files=True,
        type=["png", "jpg", "jpeg"],
        key="additional_uploader",
    )

    if additional_files:
        st.session_state.product["additional_images"] = []

        cols = st.columns(3)
        for idx, uploaded_file in enumerate(additional_files):
            image_bytes = BytesIO(uploaded_file.read())
            st.session_state.product["additional_images"].append(image_bytes)

            image_bytes.seek(0)
            col_idx = idx % 3
            with cols[col_idx]:
                image = Image.open(image_bytes)
                st.image(image, caption=f"Additional Image {idx + 1}")
                if st.button(f"Remove Image {idx + 1}", key=f"remove_{idx}"):
                    st.session_state.product["additional_images"].pop(idx)
                    st.rerun()


# S3 Bucket Management UI
def list_buckets_tab():
    st.header("List Buckets")
    if st.button("Refresh Bucket List"):
        response = make_api_request("/buckets/")
        if response:
            st.success("Successfully retrieved buckets!")
            st.json(response)


def create_bucket_tab():
    st.header("Create Bucket")
    with st.form("create_bucket_form"):
        bucket_name = st.text_input("Bucket Name (optional)")
        region = st.selectbox(
            "Region",
            ["us-east-1", "us-west-1", "us-west-2", "eu-west-1", "eu-central-1"],
        )
        submit_button = st.form_submit_button("Create Bucket")

        if submit_button:
            params = {"region": region}
            if bucket_name:
                params["bucket_name"] = bucket_name
            response = make_api_request("/buckets/create", method="POST", params=params)
            if response:
                st.success("Bucket created successfully!")
                st.json(response)


def bucket_details_tab():
    st.header("Bucket Details")
    bucket_name = st.text_input("Enter Bucket Name")
    if bucket_name and st.button("Get Details"):
        response = make_api_request(f"/buckets/{bucket_name}")
        if response:
            st.success(f"Retrieved details for bucket: {bucket_name}")
            st.json(response)


def create_bucket_with_folder_tab():
    st.header("Create Bucket with Folder")
    with st.form("create_bucket_with_folder_form"):
        bucket_name = st.text_input("Bucket Name (optional)")
        region = st.selectbox(
            "Region",
            ["us-east-1", "us-west-1", "us-west-2", "eu-west-1", "eu-central-1"],
        )
        folder_name = st.text_input("Folder Name", value="new-folder/")
        submit_button = st.form_submit_button("Create Bucket with Folder")

        if submit_button:
            params = {"region": region, "folder_name": folder_name}
            if bucket_name:
                params["bucket_name"] = bucket_name
            response = make_api_request(
                "/buckets/create-with-folder", method="POST", params=params
            )
            if response:
                st.success("Bucket and folder created successfully!")
                st.json(response)


def get_image_urls_tab():
    st.header("Get Public Image URLs in Folder")
    with st.form("get_image_urls_form"):
        bucket_name = st.text_input("Bucket Name")
        folder_name = st.text_input("Folder Name")
        submit_button = st.form_submit_button("Get Image URLs")

        if submit_button:
            if not bucket_name or not folder_name:
                st.error("Please provide both bucket and folder names.")
            else:
                response = make_api_request(
                    f"/buckets/{bucket_name}/folders/{folder_name}/images-urls"
                )
                if response:
                    st.success("Image URLs retrieved successfully!")
                    st.json(response)
                else:
                    st.error("Failed to retrieve image URLs.")


def get_folder_contents_tab():
    st.header("Get Folder Contents")
    with st.form("get_folder_contents_form"):
        bucket_name = st.text_input("Bucket Name")
        folder_name = st.text_input("Folder Name")
        submit_button = st.form_submit_button("Get Folder Contents")

        if submit_button:
            if not bucket_name or not folder_name:
                st.error("Please provide both bucket and folder names.")
            else:
                response = make_api_request(
                    f"/buckets/{bucket_name}/folders/{folder_name}/contents"
                )
                if response:
                    st.success("Folder contents retrieved successfully!")
                    st.json(response)
                else:
                    st.error("Failed to retrieve folder contents.")


def list_all_folders_tab():
    st.header("List All Folders in Bucket")
    with st.form("list_all_folders_form"):
        bucket_name = st.text_input("Bucket Name")
        submit_button = st.form_submit_button("List Folders")

        if submit_button:
            if not bucket_name:
                st.error("Please provide a bucket name.")
            else:
                response = make_api_request(f"/buckets/{bucket_name}/folders")
                if response:
                    st.success("Folders retrieved successfully!")
                    st.json(response)
                else:
                    st.error("Failed to retrieve folders.")


# Add this new function after the other tab functions
def delete_product_tab():
    st.header("Delete Product")
    try:
        product_manager = ProductManager()

        # Add a key to session state to track deletion success
        if "delete_success" not in st.session_state:
            st.session_state.delete_success = False

        with st.form("delete_product_form", clear_on_submit=True):
            folder_name = st.text_input(
                "Product Folder Name",
                help="Enter the folder name (e.g., strength-and-honor-7a5671cb)",
            )
            st.caption(
                "The folder name can be found in the product's image URLs or from the product preview"
            )

            confirm = st.checkbox("I confirm that I want to delete this product")
            submit_button = st.form_submit_button("Delete Product")

            if submit_button:
                if not folder_name:
                    st.error("Please provide a product folder name.")
                elif not confirm:
                    st.error(
                        "Please confirm the deletion by checking the confirmation box."
                    )
                else:
                    success, message = product_manager.delete_product(folder_name)
                    if success:
                        st.session_state.delete_success = True
                        st.success(message)
                        # Force a rerun to clear the form
                        st.rerun()
                    else:
                        st.error(message)

        # Clear the success flag after rerun
        if st.session_state.delete_success:
            st.session_state.delete_success = False

    except Exception as e:
        st.error(f"Error initializing product manager: {str(e)}")


def main():
    init_session_state()

    # Sidebar
    st.sidebar.title("Management Portal")

    if st.session_state.authenticated:
        st.sidebar.success("🟢 Authenticated")

        # Page Selection
        st.session_state.current_page = st.sidebar.radio(
            "Select Page", ["Product Management", "S3 Bucket Management"]
        )

        # Logout Button
        if st.sidebar.button("Logout"):
            st.session_state.token = None
            st.session_state.authenticated = False
            st.rerun()

        # API Status
        try:
            requests.get(f"{API_BASE_URL}/buckets/")
            st.sidebar.success("🟢 API Connected")
        except requests.RequestException:
            st.sidebar.error("🔴 API Unavailable")

        # Main Content Area
        if st.session_state.current_page == "Product Management":
            st.title("Product Management")
            try:
                product_manager = ProductManager()

                with st.container():
                    create_product_form(product_manager)
                    st.markdown("---")

                    st.subheader("Product Images")
                    handle_image_upload()
                    st.markdown("---")

                    # Action Buttons and Results Section
                    col1, col2 = st.columns([1, 4])

                    with col1:
                        if st.button(
                            "Reset Form", type="secondary", use_container_width=True
                        ):
                            # Clear all form data
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

                            # Clear results
                            st.session_state.product_creation_result = None
                            st.session_state.last_created_sku = None
                            st.session_state.last_created_preview = None

                            st.session_state.image_previews = []
                            st.rerun()

                    with col2:
                        if st.button(
                            "Create Product", type="primary", use_container_width=True
                        ):
                            if handle_product_creation(product_manager):
                                st.rerun()

                # Results Section
                if (
                    st.session_state.product_creation_result
                    or st.session_state.last_created_sku
                    or st.session_state.last_created_preview
                ):

                    st.markdown("---")
                    st.subheader("Last Created Product Results")

                    # Display success/error message
                    if st.session_state.product_creation_result:
                        st.success(st.session_state.product_creation_result)

                    # Display SKU
                    if st.session_state.last_created_sku:
                        st.info(f"Generated SKU: {st.session_state.last_created_sku}")

                    # Display Preview
                    if st.session_state.last_created_preview:
                        with st.expander("Product Preview", expanded=True):
                            st.json(st.session_state.last_created_preview)

            except Exception as e:
                st.error(f"Product Management Error: {str(e)}")
                logger.error(f"Product Management Error: {str(e)}")

        else:  # S3 Bucket Management
            st.title("S3 Bucket Management")
            tabs = st.tabs(
                [
                    "List Buckets",
                    "Create Bucket",
                    "Bucket Details",
                    "Create with Folder",
                    "Get Image URLs",
                    "Get Folder Contents",
                    "List All Folders",
                    "Delete Product",
                ]
            )

            with tabs[0]:
                list_buckets_tab()

            with tabs[1]:
                create_bucket_tab()

            with tabs[2]:
                bucket_details_tab()

            with tabs[3]:
                create_bucket_with_folder_tab()

            with tabs[4]:
                get_image_urls_tab()

            with tabs[5]:
                get_folder_contents_tab()

            with tabs[6]:
                list_all_folders_tab()

            with tabs[7]:
                delete_product_tab()

    else:
        # Show login form if not authenticated
        login_form()


def handle_product_creation(product_manager: ProductManager) -> bool:
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
            st.session_state.product_creation_result = "Please enter a product title"
            return False

        if (
            "thumbnail" not in st.session_state.product
            or st.session_state.product["thumbnail"] is None
        ):
            st.session_state.product_creation_result = "Please upload a thumbnail image"
            return False

        thumbnail_url, main_image_url, additional_image_urls, unique_id = (
            product_manager.upload_images_to_s3(
                st.session_state.product["thumbnail"],
                st.session_state.product["main_image"],
                st.session_state.product.get("additional_images", []),
                product_data["title"],
            )
        )

        if thumbnail_url is None:
            st.session_state.product_creation_result = (
                "Failed to upload thumbnail image"
            )
            return False

        # Generate SKU before insert
        sku = product_manager.generate_sku(
            product_data["title"],
            product_data["category"],
            product_data["color"],
            product_data["type"],
        )

        if product_manager.insert_product(
            product_data,
            thumbnail_url,
            main_image_url,
            additional_image_urls,
            unique_id,
        ):
            # Store results in session state
            st.session_state.product_creation_result = "Product created successfully!"
            st.session_state.last_created_sku = sku
            st.session_state.last_created_preview = {
                **product_data,
                "sku": sku,
                "thumbnail_image": thumbnail_url,
                "main_image": main_image_url,
                "additional_images": additional_image_urls,
                "unique_id": unique_id,
            }
            return True

        st.session_state.product_creation_result = (
            "Failed to create product in database"
        )
        return False

    except Exception as e:
        st.session_state.product_creation_result = f"Error creating product: {str(e)}"
        logger.error(f"Error creating product: {str(e)}")
        return False


if __name__ == "__main__":
    main()
