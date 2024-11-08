import base64
from io import BytesIO
from typing import List

from PIL import Image

import streamlit as st

# Constants
COLOR_OPTIONS = ["red", "blue", "green", "black", "white"]
TYPE_OPTIONS = ["T-shirt", "Hoodie", "Long Sleeve", "Other"]


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
        help="Upload one or more product images",
    )

    if uploaded_files:
        # Clear existing previews
        st.session_state.image_previews = []
        st.session_state.product["images"] = []

        # Create new image preview grid
        cols = st.columns(3)
        for idx, uploaded_file in enumerate(uploaded_files):
            # Save image to session state
            st.session_state.product["images"].append(uploaded_file)

            # Create preview
            col_idx = idx % 3
            with cols[col_idx]:
                image = Image.open(uploaded_file)
                st.image(image, caption=f"Image {idx + 1}", use_column_width=True)
                if st.button(
                    "🗑️ Remove", key=f"remove_{idx}", help=f"Remove image {idx + 1}"
                ):
                    st.session_state.product["images"].pop(idx)
                    st.rerun()


def create_product_form():
    """Create and display the product form."""
    with st.form("product_form", clear_on_submit=False):
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

        # Image Upload Section
        st.subheader("Product Images")
        handle_image_upload()

        # Action Buttons Container
        button_col1, button_col2 = st.columns([1, 4])

        with button_col1:
            cancel_button = st.form_submit_button(
                "Cancel",
                type="secondary",
                use_container_width=True,
                help="Cancel and reset form",
            )

        with button_col2:
            submit_button = st.form_submit_button(
                "Create Product", type="primary", use_container_width=True
            )

        if submit_button:
            # Update session state with form values
            for key in st.session_state.product.keys():
                if key != "images":  # Handle images separately
                    st.session_state.product[key] = st.session_state[key]

            # Here you would normally send the data to your backend
            try:
                # Simulate API call
                st.success("Product created successfully!")
                # Show product preview
                with st.expander("Product Preview", expanded=True):
                    st.json(st.session_state.product)
            except Exception as e:
                st.error(f"Failed to create product: {str(e)}")

        if cancel_button:
            # Reset form
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


def main():
    # Custom styling
    st.markdown(
        """
        <style>
        .main .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
            padding-left: 5rem;
            padding-right: 5rem;
        }
        </style>
    """,
        unsafe_allow_html=True,
    )

    st.title("Create New Product")
    st.markdown("---")

    # Initialize session state
    init_session_state()

    # Create main container with form
    with st.container():
        create_product_form()


if __name__ == "__main__":
    main()
