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
            "images": [],
        }
    if "image_previews" not in st.session_state:
        st.session_state.image_previews = []


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

    def upload_images_to_s3(
        self, images: List[BytesIO], product_title: str
    ) -> Tuple[str, List[str]]:
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

                if idx == 0:
                    thumbnail_url = url
                else:
                    image_urls.append(url)
            except Exception as e:
                st.error(f"Failed to upload image {idx}: {str(e)}")

        return thumbnail_url, image_urls

    def insert_product(
        self, product_data: dict, thumbnail_url: str, additional_image_urls: List[str]
    ) -> bool:
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
                "additional_images": json.dumps(additional_image_urls),
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
    uploaded_files = st.file_uploader(
        "Upload Product Images (First image will be the thumbnail)",
        accept_multiple_files=True,
        type=["png", "jpg", "jpeg"],
        key="image_uploader",
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

                    col1, col2 = st.columns([1, 4])

                    with col1:
                        if st.button(
                            "Reset Form", type="secondary", use_container_width=True
                        ):
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
                            if handle_product_creation(product_manager):
                                st.rerun()

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
            st.error("Please enter a product title")
            return False

        if not st.session_state.product["images"]:
            st.warning("Please upload at least one product image")
            return False

        thumbnail_url, additional_image_urls = product_manager.upload_images_to_s3(
            st.session_state.product["images"], product_data["title"]
        )

        if product_manager.insert_product(
            product_data, thumbnail_url, additional_image_urls
        ):
            st.success("Product created successfully!")

            # Generate and display SKU
            sku = product_manager.generate_sku(
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
            return True

        st.error("Failed to create product in database")
        return False

    except Exception as e:
        st.error(f"Error creating product: {str(e)}")
        logger.error(f"Error creating product: {str(e)}")
        return False


if __name__ == "__main__":
    main()
