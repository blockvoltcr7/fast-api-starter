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
        "Upload Images",
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
            # Save image to session state
            st.session_state.product["images"].append(uploaded_file)

            # Create preview
            col_idx = idx % 3
            with cols[col_idx]:
                image = Image.open(uploaded_file)
                st.image(image, caption=f"Image {idx + 1}")
                if st.button(f"Remove Image {idx + 1}", key=f"remove_{idx}"):
                    st.session_state.product["images"].pop(idx)
                    st.rerun()


def create_product_form():
    """Create and display the product form."""
    with st.form("product_form", clear_on_submit=False):
        # Title
        st.text_input(
            "Title",
            key="title",
            value=st.session_state.product["title"],
            help="Enter the product title",
        )

        # Description
        st.text_area(
            "Description",
            key="description",
            value=st.session_state.product["description"],
            help="Enter the product description",
        )

        # Create two columns for color and type
        col1, col2 = st.columns(2)

        with col1:
            # Color
            st.selectbox(
                "Color",
                options=COLOR_OPTIONS,
                key="color",
                index=COLOR_OPTIONS.index(st.session_state.product["color"]),
            )

        with col2:
            # Type
            st.selectbox(
                "Type",
                options=TYPE_OPTIONS,
                key="type",
                index=TYPE_OPTIONS.index(st.session_state.product["type"]),
            )

        # Create two columns for price and material
        col3, col4 = st.columns(2)

        with col3:
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

        with col4:
            # Material
            st.text_input(
                "Material",
                key="material",
                value=st.session_state.product["material"],
                help="Enter the product material",
            )

        # In Stock Switch
        st.toggle(
            "In Stock", key="in_stock", value=st.session_state.product["in_stock"]
        )

        # Submit button
        submit_button = st.form_submit_button("Create Product")

        if submit_button:
            # Update session state with form values
            for key in st.session_state.product.keys():
                if key != "images":  # Handle images separately
                    st.session_state.product[key] = st.session_state[key]

            # Here you would normally send the data to your backend
            try:
                # Simulate API call
                st.success("Product created successfully!")
                st.json(st.session_state.product)  # Display the product data
            except Exception as e:
                st.error(f"Failed to create product: {str(e)}")


def main():
    st.title("Create New Product")

    # Initialize session state
    init_session_state()

    # Create main card/container
    with st.container():
        st.markdown("### Product Details")

        # Image upload section
        st.markdown("### Product Images")
        handle_image_upload()

        # Main form
        create_product_form()

        # Cancel button (outside form)
        if st.button("Cancel"):
            # Reset form
            for key in st.session_state.product.keys():
                st.session_state.product[key] = ""
                if key == "in_stock":
                    st.session_state.product[key] = True
                elif key == "price":
                    st.session_state.product[key] = 0.0
                elif key == "color":
                    st.session_state.product[key] = "red"
                elif key == "type":
                    st.session_state.product[key] = "T-shirt"
            st.session_state.image_previews = []
            st.rerun()


if __name__ == "__main__":
    main()
