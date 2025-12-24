"""
On-Demand Report Regeneration API
Allows regenerating reports from database without storing them permanently
"""
import os
import logging
from flask import Blueprint, jsonify, send_file, current_app
from app.models import Submission
from common.db_utils import get_submission_db

logger = logging.getLogger(__name__)

reports_bp = Blueprint('reports', __name__, url_prefix='/api/reports')


@reports_bp.route('/regenerate/<submission_id>/excel', methods=['GET'])
def regenerate_excel(submission_id):
    """
    Regenerate Excel report from submission data on-demand
    No permanent storage - report is generated fresh each time
    """
    try:
        # Get submission from database
        submission_data = get_submission_db(submission_id)
        if not submission_data:
            return jsonify({'error': 'Submission not found'}), 404
        
        module_type = submission_data.get('module_type')
        form_data = submission_data.get('form_data', {})
        
        # Generate report based on module type
        if module_type == 'civil':
            from module_civil.civil_generators import create_excel_report
        elif module_type == 'hvac_mep':
            from module_hvac_mep.hvac_generators import create_excel_report
        elif module_type == 'cleaning':
            from module_cleaning.cleaning_generators import create_excel_report
        else:
            return jsonify({'error': f'Unknown module type: {module_type}'}), 400
        
        # Generate report in temporary location
        temp_dir = current_app.config.get('GENERATED_DIR')
        report_path = create_excel_report(form_data, temp_dir)
        
        # Send file and delete after sending
        return send_file(
            report_path,
            as_attachment=True,
            download_name=os.path.basename(report_path),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
    except Exception as e:
        logger.error(f"Failed to regenerate Excel: {e}")
        return jsonify({'error': str(e)}), 500


@reports_bp.route('/regenerate/<submission_id>/pdf', methods=['GET'])
def regenerate_pdf(submission_id):
    """
    Regenerate PDF report from submission data on-demand
    No permanent storage - report is generated fresh each time
    """
    try:
        # Get submission from database
        submission_data = get_submission_db(submission_id)
        if not submission_data:
            return jsonify({'error': 'Submission not found'}), 404
        
        module_type = submission_data.get('module_type')
        form_data = submission_data.get('form_data', {})
        
        # Generate report based on module type
        if module_type == 'civil':
            from module_civil.civil_generators import create_pdf_report
        elif module_type == 'hvac_mep':
            from module_hvac_mep.hvac_generators import create_pdf_report
        elif module_type == 'cleaning':
            from module_cleaning.cleaning_generators import create_pdf_report
        else:
            return jsonify({'error': f'Unknown module type: {module_type}'}), 400
        
        # Generate report in temporary location
        temp_dir = current_app.config.get('GENERATED_DIR')
        report_path = create_pdf_report(form_data, temp_dir)
        
        # Send file and delete after sending
        return send_file(
            report_path,
            as_attachment=True,
            download_name=os.path.basename(report_path),
            mimetype='application/pdf'
        )
        
    except Exception as e:
        logger.error(f"Failed to regenerate PDF: {e}")
        return jsonify({'error': str(e)}), 500


@reports_bp.route('/list/<module_type>', methods=['GET'])
def list_reports(module_type):
    """
    List all submissions for a module
    """
    try:
        from app.models import Submission
        
        submissions = Submission.query.filter_by(module_type=module_type).order_by(Submission.created_at.desc()).limit(100).all()
        
        return jsonify({
            'module': module_type,
            'count': len(submissions),
            'submissions': [s.to_dict() for s in submissions]
        })
        
    except Exception as e:
        logger.error(f"Failed to list submissions: {e}")
        return jsonify({'error': str(e)}), 500


@reports_bp.route('/submission/<submission_id>', methods=['GET'])
def get_submission_details(submission_id):
    """
    Get submission details with regeneration links
    """
    try:
        submission_data = get_submission_db(submission_id)
        if not submission_data:
            return jsonify({'error': 'Submission not found'}), 404
        
        # Add regeneration URLs
        submission_data['reports'] = {
            'excel_url': f"/api/reports/regenerate/{submission_id}/excel",
            'pdf_url': f"/api/reports/regenerate/{submission_id}/pdf"
        }
        
        return jsonify(submission_data)
        
    except Exception as e:
        logger.error(f"Failed to get submission: {e}")
        return jsonify({'error': str(e)}), 500
