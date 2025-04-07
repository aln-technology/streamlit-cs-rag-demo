# streamlit_app.py

import streamlit as st
import pdfplumber
import json
import io
import openai
from collections import defaultdict
from PIL import ImageDraw
from extraction_config import (
    patterns,
    shared_schema,
    CLASSIFICATION_MAPPING,
    CLASSIFICATION_COLORS,
)
from typing import List

# --- Set up API key ---
api_key = st.secrets["OPENAI_API_KEY"]
client = openai.OpenAI(api_key=api_key)

# --- Streamlit App ---
st.title("Manufacturing RFQ PMI Extraction")

uploaded_file = st.file_uploader("Upload a 2D manufacturing diagram PDF", type=["pdf"])
if uploaded_file:
    with st.spinner("Processing PDF and extracting information..."):
        pdf_bytes = uploaded_file.read()
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            first_page = pdf.pages[0]
            words = first_page.extract_words()
            image = first_page.to_image()

            # Convert to PIL Image for drawing
            pil_image = image.annotated.copy()  # image.annotated is already a PIL Image
            draw = ImageDraw.Draw(pil_image)

            # Define colors for different categories
            category_colors = {
                "material": (255, 0, 0),  # Red
                "finish": (0, 255, 0),  # Green
                "general_tolerance": (0, 0, 255),  # Blue
                "threads": (255, 165, 0),  # Orange
                "diameters": (128, 0, 128),  # Purple
                "standards": (255, 192, 203),  # Pink
                "weld_requirements": (0, 128, 128),  # Teal
            }

            # Process text and generate merged_fields first
            all_text = []
            note_lines = []
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    lines = text.split("\n")
                    all_text.extend(lines)
                    for line in lines:
                        if any(
                            k in line.upper()
                            for k in ["NOTE", "WELD", "COATING", "SURFACE"]
                        ):
                            note_lines.append(line.strip())

            text_blob = "\n".join(all_text)
            notes_blob = "\n".join(note_lines)

            # --- Regex pass ---
            regex_extracted = defaultdict(set)
            for label, pattern in patterns.items():
                for match in pattern.findall(text_blob):
                    match_text = match[0] if isinstance(match, tuple) else match
                    if match_text.upper() != "ING":
                        regex_extracted[label].add(match_text.strip())

            # --- LLM passes ---
            def llm_pass(prompt_text, name):
                try:
                    system_prompt = """Extract ALL quote-relevant manufacturing data. Follow these rules:
1. Each field MUST contain:
   - An array of ALL standardized values found (keep these concise and filterable)
   - A detailed notes field that provides comprehensive context
   - A sources array containing the evidence for each extraction
   - For example, rather than 6-12in pipe, extract 6 inch pipe, 8 inch pipe, 10 inch pipe, 12 inch pipe
   - Specify whatever the diameter is for. E.g. 6 inch pipe, not just 6 inch
2. Values should be normalized and standardized but MUST be comprehensive:
   - Extract ALL instances of each type of value, not just a representative sample
   - Include ALL variations and instances, even if they seem similar
   - Remove unnecessary details and context from values
   - Split complex requirements into separate values
   - Use standard units and formats
   - Use uppercase for standards and specifications
3. Notes field should be comprehensive and include:
   - Full context and requirements
   - Application-specific details
   - Location or part-specific information
   - Relationships between different values
   - Special instructions or considerations
   - Any caveats or conditions
4. Sources must include for EVERY value:
   - The exact text snippet from the document that supports the extraction
   - Which value it supports
   - A few words of surrounding context
5. Example format showing multiple similar values:
   "threads": {
     "values": ["M6x1.0", "M6x1.0", "M8x1.25", "M8x1.25", "1/4-20 UNC"],
     "notes": "Multiple M6 and M8 threaded holes throughout. M6 holes on front face, M8 on back face, 1/4-20 UNC on mounting bracket.",
     "sources": [
       {
         "text": "M6x1.0 threaded hole",
         "value": "M6x1.0",
         "context": "Front face: M6x1.0 threaded hole"
       },
       {
         "text": "M6x1.0 thread",
         "value": "M6x1.0",
         "context": "Second M6x1.0 thread on front face"
       },
       {
         "text": "M8x1.25",
         "value": "M8x1.25",
         "context": "Back face: 2x M8x1.25"
       }
     ]
   }
   
IMPORTANT: Do not summarize or reduce multiple instances to a single value. Extract and list ALL instances, even if they are identical."""

                    response = client.responses.create(
                        model="gpt-4o-2024-08-06",
                        input=[
                            {
                                "role": "system",
                                "content": system_prompt,
                            },
                            {"role": "user", "content": prompt_text},
                        ],
                        text={
                            "format": {
                                "type": "json_schema",
                                "name": name,
                                "schema": shared_schema,
                                "strict": True,
                            }
                        },
                    )
                    return json.loads(response.output_text)
                except Exception as e:
                    return {"error": str(e)}

            notes_data = llm_pass(notes_blob, "notes_extraction")
            doc_data = llm_pass(text_blob, "doc_extraction")

            # --- Merge all fields ---
            merge_prompt = {
                "role": "user",
                "content": (
                    "Merge field-level extractions from document-wide LLM, notes-only LLM, and regex. "
                    "Return final values only, deduplicated and domain-cleaned.\n\n"
                    "Rules:\n"
                    "1. Standardize and normalize all values\n"
                    "2. Remove duplicates and similar values\n"
                    "3. Group related values that represent alternatives\n"
                    "4. Move contextual details to notes\n"
                    "5. Keep values concise and filterable\n\n"
                    f"Document LLM:\n{json.dumps(doc_data)}\n\n"
                    f"Notes LLM:\n{json.dumps(notes_data)}\n\n"
                    f"Regex:\n{json.dumps({k: list(v) for k, v in regex_extracted.items()})}"
                ),
            }

            merge_response = client.responses.create(
                model="gpt-4o-2024-08-06",
                input=[
                    {
                        "role": "system",
                        "content": "Return the most complete and accurate merged manufacturing information in JSON. "
                        "Ensure values are standardized and normalized, with contextual details in notes.",
                    },
                    merge_prompt,
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "merged_fields",
                        "schema": shared_schema,
                        "strict": True,
                    }
                },
            )

            merged_fields = json.loads(merge_response.output_text)

            # Add function to find text locations
            def find_text_locations(page, text, context):
                """Find the bounding box for a text snippet within a page."""
                words = page.extract_words()
                best_match = None  # Initialize best_match at the start

                # First try exact match
                for word in words:
                    if text.lower() in word["text"].lower():
                        return {
                            "x0": word["x0"],
                            "y0": word["top"],
                            "x1": word["x1"],
                            "y1": word["bottom"],
                        }

                # If no exact match, try fuzzy matching with context
                if context:
                    best_score = 0
                    for word in words:
                        if any(
                            part.lower() in word["text"].lower()
                            for part in text.split()
                        ):
                            # Simple scoring - can be improved
                            score = sum(
                                1
                                for part in text.split()
                                if part.lower() in word["text"].lower()
                            )
                            if score > best_score:
                                best_score = score
                                best_match = word

                if best_match:
                    return {
                        "x0": best_match["x0"],
                        "y0": best_match["top"],
                        "x1": best_match["x1"],
                        "y1": best_match["bottom"],
                    }

                return None

            # Draw all annotations on the image
            # First, draw regex matches
            for word in words:
                text = word["text"].upper()
                x0, top, x1, bottom = (
                    word["x0"],
                    word["top"],
                    word["x1"],
                    word["bottom"],
                )

                # Check each pattern
                for category, pattern in patterns.items():
                    if pattern.search(text):
                        color = category_colors.get(category, (128, 128, 128))
                        # Draw thicker rectangle with padding
                        padding = 6
                        draw.rectangle(
                            [
                                x0 - padding,
                                top - padding,
                                x1 + padding,
                                bottom + padding,
                            ],
                            outline=color,
                            width=6,
                        )
                        break  # Stop after first match

            # Then, process and draw source locations
            source_locations = []
            for field_name, field_data in merged_fields.items():
                for source in field_data.get("sources", []):
                    location = find_text_locations(
                        first_page, source["text"], source["context"]
                    )
                    if location:
                        source_locations.append(
                            {
                                "field": field_name,
                                "value": source["value"],
                                "bbox": location,
                            }
                        )
                        # Draw the box immediately
                        draw.rectangle(
                            [
                                (location["x0"], location["y0"]),
                                (location["x1"], location["y1"]),
                            ],
                            outline=category_colors.get(field_name, (128, 128, 128)),
                            width=3,
                        )

            # Now display the image with all annotations
            st.markdown("### Drawing and Extracted Information")

            # Display the image at full width
            st.image(
                pil_image,
                caption="Page 1 with Extracted Information Highlighted",
                use_container_width=True,
            )

            # Add minimal custom CSS for modern look
            st.markdown(
                """
                <style>
                    .chip {
                        display: inline-block;
                        padding: 4px 12px;
                        margin: 4px 4px 4px 0;
                        border-radius: 16px;
                        background: linear-gradient(135deg, rgba(173, 216, 230, 0.2), rgba(135, 206, 235, 0.2));
                        color: #262730;
                        font-size: 14px;
                        font-weight: 500;
                        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
                        border: 1px solid rgba(135, 206, 235, 0.3);
                        transition: all 0.2s ease;
                    }
                    
                    .chip:hover {
                        background: linear-gradient(135deg, rgba(173, 216, 230, 0.3), rgba(135, 206, 235, 0.3));
                        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                        border-color: rgba(135, 206, 235, 0.5);
                    }
                    
                    .notes-container {
                        margin: 12px 0;
                        padding: 12px 16px;
                        background: linear-gradient(135deg, rgba(173, 216, 230, 0.15), rgba(135, 206, 235, 0.15));
                        border-radius: 8px;
                        border-left: 3px solid #4ECDC4;
                    }
                    
                    .notes-header {
                        color: #262730;
                        font-weight: 600;
                        margin-bottom: 8px;
                    }

                    .notes-content {
                        color: #262730;
                        line-height: 1.5;
                    }

                    .classification-chip {
                        display: inline-block;
                        padding: 4px 12px;
                        margin: 4px 4px 4px 0;
                        border-radius: 16px;
                        color: white;
                        font-size: 14px;
                        font-weight: 500;
                        box-shadow: 0 1px 2px rgba(0,0,0,0.1);
                    }

                    .source-reference {
                        margin: 8px 0;
                        padding: 8px 12px;
                        background: linear-gradient(135deg, rgba(173, 216, 230, 0.1), rgba(135, 206, 235, 0.1));
                        border-radius: 6px;
                        border-left: 2px solid #4ECDC4;
                    }

                    .source-text {
                        color: #262730;
                        font-style: italic;
                    }

                    .source-value {
                        color: #4ECDC4;
                        font-weight: 500;
                    }
                </style>
            """,
                unsafe_allow_html=True,
            )

            # Add legend
            st.markdown("**Legend**")
            legend_cols = st.columns(4)
            for i, (category, color) in enumerate(category_colors.items()):
                with legend_cols[i % 4]:
                    st.markdown(
                        f"<div style='display: flex; align-items: center; margin: 2px 0;'>"
                        f"<div style='width: 8px; height: 8px; background-color: rgb{color}; margin-right: 4px;'></div>"
                        f"<div style='font-size: 12px;'>{category.replace('_', ' ').title()}</div>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )

            def get_classifications(field_name: str, values: List[str]) -> List[str]:
                """Get classifications for a field's values."""
                if field_name not in CLASSIFICATION_MAPPING:
                    return []

                classifier = CLASSIFICATION_MAPPING[field_name]
                classifications = set()

                for value in values:
                    result = classifier(value)
                    if result:
                        if isinstance(result, list):
                            classifications.update(result)
                        else:
                            classifications.add(result)

                return sorted(list(classifications))

            # Update the render_section function
            def render_section(title, field_data):
                if not field_data["values"]:
                    return

                st.markdown(f"#### {title}")

                # Display values as chips first
                chips_html = " ".join(
                    [
                        f"<span class='chip'>{value}</span>"
                        for value in field_data["values"]
                    ]
                )
                st.markdown(chips_html, unsafe_allow_html=True)

                # Get and display classifications after values
                classifications = get_classifications(
                    title.lower(), field_data["values"]
                )
                if classifications:
                    # Define tooltip content based on field type
                    tooltip_content = {
                        "diameters": "Class A: 6-8 inch pipe, Class B: 8-10 inch pipe, Class C: 10-12 inch pipe",
                        "threads": "Light Duty Stud: ≤20mm, Heavy Duty Stud: >20mm, Standard Anchor: ≤25mm, Heavy Duty Anchor: >25mm, Standard Hole: ≤20mm, Large Hole: >20mm",
                        "material": "Standard Stainless: 304 series, Marine Grade: 316 series, General Stainless: Other grades, Aircraft Aluminum: 6061, General Aluminum: Other grades, Brass: Decorative/Corrosion Resistant, Bronze: High Strength/Corrosion Resistant, PEEK: High Performance Plastic",
                    }.get(
                        title.lower(),
                        "No classification criteria defined for this field.",
                    )

                    st.markdown("**Classification**", help=tooltip_content)
                    classification_chips = []
                    for classification in classifications:
                        color = CLASSIFICATION_COLORS.get(classification, "#f8f9fa")
                        classification_chips.append(
                            f"<span class='classification-chip' style='background-color: {color};'>{classification}</span>"
                        )
                    st.markdown(" ".join(classification_chips), unsafe_allow_html=True)

                # Show notes if present and not empty
                if field_data.get("notes") and field_data["notes"].strip():
                    notes_html = f"""
                        <div class='notes-container'>
                            <div class='notes-header'>Additional Details</div>
                            <div class='notes-content'>{field_data["notes"]}</div>
                        </div>
                    """
                    st.markdown(notes_html, unsafe_allow_html=True)

                # Show sources in a separate section if present
                if field_data.get("sources"):
                    with st.expander("Source References", expanded=False):
                        for source in field_data["sources"]:
                            source_html = f"""
                                <div class='source-reference'>
                                    <span class='source-text'>"{source['text']}"</span> → 
                                    <span class='source-value'>{source['value']}</span>
                                </div>
                            """
                            st.markdown(source_html, unsafe_allow_html=True)

            # Create two columns for the sections
            col1, col2 = st.columns(2)

            # Render sections in two columns
            with col1:
                render_section("Material", merged_fields["material"])
                render_section("Surface Treatment", merged_fields["finish"])
                render_section("Tolerances", merged_fields["general_tolerance"])
                render_section("Surface Roughness", merged_fields["surface_roughness"])
                render_section("Threads", merged_fields["threads"])

            with col2:
                render_section("Diameters", merged_fields["diameters"])
                render_section("Standards", merged_fields["standards"])
                render_section("Weld Requirements", merged_fields["weld_requirements"])
                render_section("Cost Drivers", merged_fields["cost_drivers"])

            with st.expander("🔍 Debug Info (Raw Outputs)"):
                st.markdown("**LLM Notes Pass**")
                st.json(notes_data)
                st.markdown("**LLM Document Pass**")
                st.json(doc_data)
                st.markdown("**Regex Pass**")
                st.json({k: list(v) for k, v in regex_extracted.items()})
