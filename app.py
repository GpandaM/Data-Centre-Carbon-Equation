#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Flask Application for Data Center Carbon Footprint Calculator
This is the main application file that serves the web interface.
"""

import os
import logging
import json
from datetime import datetime
from flask import Flask, render_template, request, redirect, flash, jsonify, url_for, Response
from werkzeug.utils import secure_filename

# Import custom modules
from carbon_calculator import DataCenterCarbonCalculator
# from carbon_calculator import DataLoader
from carbon_calculator import CarbonFactors

# Configuration
UPLOAD_FOLDER = 'data/uploads'
ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize Flask app
# app = Flask(__name__)
# app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
# app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  ## 16MB max upload size
# app.secret_key = 'carbon_calculator_secret_key'  ## For flash messages

# Configure Flask app
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'data/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max
app.secret_key = 'carbon_calculator_secret_key'  ## For flash messages
# app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'carbon_calculator_secret_key')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


# Initialize carbon calculator
calculator = DataCenterCarbonCalculator()


def allowed_file(filename):
    """Check if file has allowed extension"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def make_json_serializable(obj):
    """Recursively convert non-JSON-serializable objects to serializable types."""
    import decimal
    import numpy as np
    if isinstance(obj, (decimal.Decimal, np.floating)):
        return float(obj)
    elif isinstance(obj, (np.integer)):
        return int(obj)
    elif isinstance(obj, dict):
        return {key: make_json_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [make_json_serializable(item) for item in obj]
    elif isinstance(obj, set):
        return [make_json_serializable(item) for item in list(obj)]
    return obj


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize calculator
calculator = DataCenterCarbonCalculator()


@app.route('/', methods=['GET'])
def index():
    """Render main calculator page."""
    try:
        regions = [(region, region.capitalize()) for region, _ in CarbonFactors.get_all_regions()]
        return render_template('index.html', regions=regions)
    except Exception as e:
        logger.error("Error loading index page: %s", str(e))
        flash("Error loading page. Please try again.", "error")
        return render_template('index.html', regions=[])

@app.route('/calculate', methods=['POST'])
def calculate():
    """Process form data, file upload, or API and calculate carbon footprint."""
    try:
        data_source = request.form.get('data_source')
        if data_source not in ['manual', 'file', 'api']:
            flash('Invalid data source', 'error')
            return redirect(url_for('index'))

        if data_source == 'manual':
            data = {
                'total_electricity': request.form.get('total_electricity'),
                'pue': request.form.get('pue'),
                'renewable_percentage': request.form.get('renewable_percentage'),
                'region': request.form.get('region'),
                'num_servers': request.form.get('num_servers'),
                'cpu_utilization': request.form.get('cpu_utilization'),
                'gpu_count': request.form.get('gpu_count'),
                'gpu_utilization': request.form.get('gpu_utilization'),
                'storage_capacity': request.form.get('storage_capacity'),
                'storage_type': request.form.get('storage_type'),
                'facility_area': request.form.get('facility_area'),
                'cooling_efficiency': request.form.get('cooling_efficiency'),
                'utilization_hours': request.form.get('utilization_hours'),
                'ai_compute_hours': request.form.get('ai_compute_hours'),
            }

            from carbon_calculator import DataLoader
            processed_data = DataLoader.process_data(data)
        
        elif data_source == 'file':
            if 'file' not in request.files:
                flash('No file part', 'error')
                return redirect(url_for('index'))
            
            file = request.files['file']
            if file.filename == '':
                flash('No selected file', 'error')
                return redirect(url_for('index'))
            
            if not allowed_file(file.filename):
                flash('Invalid file type. Please upload CSV or Excel file.', 'error')
                return redirect(url_for('index'))
            
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            try:
                from carbon_calculator import DataLoader
                processed_data = DataLoader.load_excel(filepath) if filename.endswith(('.xlsx', '.xls')) else DataLoader.load_csv(filepath)
            finally:
                try:
                    os.remove(filepath)
                    logger.info("Cleaned up file: %s", filepath)
                except OSError as e:
                    logger.warning("Failed to delete file %s: %s", filepath, str(e))
        
        elif data_source == 'api':
            api_url = request.form.get('api_url')
            api_key = request.form.get('api_key')
            if not api_url:
                flash('API URL is required', 'error')
                return redirect(url_for('index'))
            
            headers = {'Authorization': f'Bearer {api_key}'} if api_key else None
            try:
                from carbon_calculator import DataLoader
                processed_data = DataLoader.load_api(api_url, headers=headers)
            except Exception as e:
                flash(f'Error loading API data: {str(e)}', 'error')
                return redirect(url_for('index'))

        logger.info("Calculating carbon footprint for data: %s", processed_data)
        results = calculator.calculate_carbon_footprint(processed_data)
        # Ensure results are JSON-serializable
        results = make_json_serializable(results)
        # Add timestamp
        results['timestamp'] = datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')
        logger.debug("Serialized results: %s", json.dumps(results))
        save_to_history(results)
        
        return render_template(
            'results.html',
            results=results,
            timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )
    
    except ValueError as ve:
        logger.error("ValueError in calculate: %s", str(ve))
        flash(str(ve), 'error')
        return redirect(url_for('index'))
    except Exception as e:
        logger.error("Unexpected error in calculate: %s", str(e))
        flash(f'Error calculating carbon footprint: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/export/<format>', methods=['POST'])
def export_results(format):
    """Export results in various formats."""
    try:
        results_str = request.form.get('results')
        if not results_str:
            logger.error("No results provided for export")
            flash('No results to export', 'error')
            return redirect(url_for('index'))
            
        # Log raw input for debugging
        logger.debug("Raw results string: %s", results_str)
        
        try:
            results = json.loads(results_str)
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON in results: %s", str(e))
            flash(f'Invalid results format: {str(e)}', 'error')
            return redirect(url_for('index'))
        
        if format == 'csv':
            return export_as_csv(results)
        elif format == 'json':
            return export_as_json(results)
        elif format == 'pdf':
            return export_as_pdf(results)
        else:
            flash(f'Unsupported export format: {format}', 'error')
            return redirect(url_for('index'))
    except Exception as e:
        logger.error("Error exporting results as %s: %s", format, str(e))
        flash(f'Error exporting results: {str(e)}', 'error')
        return redirect(url_for('index'))

def export_as_pdf(results):
    """Export results as PDF file with table layout."""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet
        from io import BytesIO

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        elements = []

        # Styles
        styles = getSampleStyleSheet()
        title_style = styles['Heading1']
        title_style.textColor = colors.HexColor("#4CAF50")  # Match index.html primary color
        normal_style = styles['Normal']
        normal_style.fontSize = 10
        header_style = styles['Heading3']
        header_style.textColor = colors.HexColor("#4CAF50")

        # Title and timestamp
        elements.append(Paragraph("Data Center Carbon Footprint Report", title_style))
        elements.append(Paragraph(
            f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            normal_style
        ))
        elements.append(Spacer(1, 12))

        # Flatten results for table display
        def flatten_results(data, parent_key=''):
            flat_data = []
            for key, value in data.items():
                new_key = f"{parent_key} {key.replace('_', ' ').title()}" if parent_key else key.replace('_', ' ').title()
                if isinstance(value, dict):
                    if 'value' in value and 'unit' in value:
                        flat_data.append([new_key, f"{value['value']:.2f} {value['unit']}"])
                    else:
                        flat_data.extend(flatten_results(value, new_key))
                else:
                    flat_data.append([new_key, str(value)])
            return flat_data

        # Create table data
        table_data = [["Category", "Value"]]
        table_data.extend(flatten_results(results))

        # Create table
        table = Table(table_data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#4CAF50")),  # Green header
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#E0E0E0")),  # Match index.html border color
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor("#F5F5F5")),  # Match index.html background
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.HexColor("#E0E0E0")),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#E0E0E0")),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(table)

        # Build PDF
        doc.build(elements)
        buffer.seek(0)

        return Response(
            buffer.getvalue(),
            mimetype="application/pdf",
            headers={"Content-disposition": "attachment; filename=carbon_footprint_results.pdf"}
        )
    except ImportError:
        logger.error("PDF export requires reportlab library")
        flash("PDF export requires reportlab library, which is not installed", 'error')
        return redirect(url_for('index'))
    except Exception as e:
        logger.error("Error generating PDF: %s", str(e))
        flash(f"Error generating PDF: {str(e)}", 'error')
        return redirect(url_for('index'))


@app.route('/history', methods=['GET'])
def history():
    """View calculation history"""
    try:
        history_data = load_history()
        return render_template('history.html', history=history_data)
    except Exception as e:
        flash(f'Error loading history: {str(e)}', 'error')
        return redirect(url_for('index'))


# @app.route('/recommendations', methods=['GET'])
# def recommendations():
#     """Get recommendations for reducing carbon footprint"""
#     current_data = request.args.get('data')
    
#     if current_data:
#         try:
#             current_data = json.loads(current_data)
#             recommendations = calculator.generate_recommendations(current_data)
#             return render_template('recommendations.html', recommendations=recommendations)
#         except Exception as e:
#             flash(f'Error generating recommendations: {str(e)}', 'error')
#             return redirect(url_for('index'))
#     else:
#         flash('No data provided for recommendations', 'error')
#         return redirect(url_for('index'))


# @app.route('/api/calculate', methods=['POST'])
# def api_calculate():
#     """API endpoint for carbon footprint calculation"""
#     try:
#         data = request.get_json()
#         if not data:
#             return jsonify({'error': 'No data provided'}), 400
            
#         processed_data = DataLoader.process_data(data)
#         results = calculator.calculate_carbon_footprint(processed_data)
        
#         return jsonify({
#             'success': True,
#             'results': results,
#             'timestamp': datetime.now().isoformat()
#         })
#     except Exception as e:
#         return jsonify({'error': str(e)}), 500


# @app.route('/api/regions', methods=['GET'])
# def api_regions():
#     """API endpoint to get all available regions and their carbon intensity factors"""
#     try:
#         regions = CarbonFactors.get_all_regions()
#         return jsonify({
#             'success': True,
#             'regions': dict(regions)
#         })
#     except Exception as e:
#         return jsonify({'error': str(e)}), 500


def export_as_csv(results):
    """Export results as CSV file"""
    from io import StringIO
    import csv
    
    output = StringIO()
    writer = csv.writer(output)
    
    # Write headers
    writer.writerow(['Metric', 'Value', 'Unit'])
    
    # Write data
    for key, value in results.items():
        if isinstance(value, dict):
            for sub_key, sub_value in value.items():
                writer.writerow([f"{key} - {sub_key}", sub_value['value'], sub_value['unit']])
        else:
            unit = results.get(f"{key}_unit", "")
            writer.writerow([key, value, unit])
    
    output.seek(0)
    from flask import Response
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=carbon_footprint_results.csv"}
    )


def export_as_json(results):
    """Export results as JSON file"""
    from flask import Response
    return Response(
        json.dumps(results, indent=4),
        mimetype="application/json",
        headers={"Content-disposition": "attachment; filename=carbon_footprint_results.json"}
    )


def save_to_history(results):
    """Save calculation results to history"""
    history_file = os.path.join('data', 'history.json')
    os.makedirs(os.path.dirname(history_file), exist_ok=True)
    
    history = []
    if os.path.exists(history_file):
        try:
            with open(history_file, 'r') as f:
                history = json.load(f)
        except:
            history = []
    
    # Add current results to history
    history_entry = {
        'timestamp': datetime.now().isoformat(),
        'results': results
    }
    
    history.append(history_entry)
    
    # Keep only the latest 100 entries
    if len(history) > 100:
        history = history[-100:]
    
    # Save history
    with open(history_file, 'w') as f:
        json.dump(history, f, indent=4)


def load_history():
    """Load calculation history"""
    history_file = os.path.join('data', 'history.json')
    
    if not os.path.exists(history_file):
        return []
    
    with open(history_file, 'r') as f:
        history = json.load(f)
    
    # Sort by timestamp (newest first)
    history.sort(key=lambda x: x['timestamp'], reverse=True)
    
    return history


@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 errors"""
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors"""
    return render_template('500.html'), 500


if __name__ == '__main__':
    # Load environment variables if available
    port = int(os.environ.get('PORT', 8080))
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    # Run the application
    app.run(host='0.0.0.0', port=port, debug=debug)