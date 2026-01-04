"""
Word Document Generation Service

CHANGE: Added anomaly detection section to reports
- New parameter: anomaly_data (optional, backward compatible)
- New method: add_anomaly_section() - Formats and adds anomaly tables
- Enhanced generate_cost_report() - Includes anomaly summary at bottom

Logic:
- Accept subscription data dictionary with any keys
- Generate cost tables for each subscription
- NEW: Add anomaly detection summary if data provided
- Anomaly section shows only days with detected anomalies
- Groups anomalies by date for clarity
"""
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import os


class DocumentGeneratorService:
    """Generate Word documents for cost reports"""
    
    def __init__(self, output_directory: str):
        self.output_directory = output_directory
        os.makedirs(output_directory, exist_ok=True)
    
    def add_table_to_doc(self, doc: Document, table_data: List[list], headers: List[str], title: str = None):
        """Add a formatted table to the Word document"""
        
        if title:
            para = doc.add_paragraph()
            run = para.add_run(title)
            run.bold = True
            run.font.size = Pt(11)
        
        # Create table
        table = doc.add_table(rows=1, cols=len(headers))
        table.style = 'Light Grid Accent 1'
        
        # Add headers
        hdr_cells = table.rows[0].cells
        for i, header in enumerate(headers):
            hdr_cells[i].text = header
            hdr_cells[i].paragraphs[0].runs[0].font.bold = True
            hdr_cells[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Add data rows
        for row_data in table_data:
            row_cells = table.add_row().cells
            for i, cell_data in enumerate(row_data):
                row_cells[i].text = str(cell_data)
                row_cells[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        doc.add_paragraph()  # Add spacing
    
    def add_anomaly_section(self, doc: Document, anomaly_data: List[Dict], threshold: float):
        """
        NEW METHOD: Add anomaly detection summary to the document.
        
        Logic:
        1. Add a section header "Anomaly Detection Summary"
        2. For each day in the anomaly data:
           - Check if any anomalies were detected
           - If yes, create a table showing:
             * Subscription name
             * Service name
             * Average cost
             * Current cost
             * Percentage change
        3. If no anomalies found for any day, add a note saying so
        
        Args:
            doc: Document object to add content to
            anomaly_data: List of anomaly detection results per day
            threshold: Threshold percentage used for detection
        """
        
        # Add section divider
        doc.add_page_break()
        
        # Add section header
        header = doc.add_heading('Anomaly Detection Summary', level=1)
        header.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Add explanation paragraph
        explanation = doc.add_paragraph()
        explanation.add_run(
            f"The following section shows cost anomalies detected during the report period. "
            f"An anomaly is flagged when a service's cost exceeds the rolling average by more than {threshold:.1f}%.\n\n"
        )
        
        # Track if any anomalies were found
        total_anomalies_found = False
        
        # Process each day
        for day_result in anomaly_data:
            date_str = day_result.get('date', 'Unknown Date')
            day_name = day_result.get('day_name', '')
            subscriptions = day_result.get('subscriptions', {})
            
            # Check if this day has any anomalies
            day_has_anomalies = False
            anomaly_rows = []
            
            for sub_name, sub_data in subscriptions.items():
                if not sub_data or not sub_data.get('has_anomalies', False):
                    continue
                
                day_has_anomalies = True
                
                # Get anomaly details
                anomalies = sub_data.get('anomalies', [])
                
                for anomaly in anomalies:
                    anomaly_rows.append([
                        sub_name,
                        anomaly['service'],
                        f"${anomaly['average_cost']:.2f}",
                        f"${anomaly['current_cost']:.2f}",
                        f"{anomaly['percent_change']:+.2f}%"
                    ])
            
            # If this day has anomalies, add a table
            if day_has_anomalies:
                total_anomalies_found = True
                
                # Add date header
                date_header = doc.add_paragraph()
                run = date_header.add_run(f"{day_name}, {date_str}")
                run.bold = True
                run.font.size = Pt(12)
                run.font.color.rgb = RGBColor(192, 0, 0)  # Red color for emphasis
                
                # Add anomaly table
                headers = ['Subscription', 'Service', 'Average Cost', 'Current Cost', 'Change %']
                self.add_table_to_doc(doc, anomaly_rows, headers)
                
                # Add summary note
                summary = doc.add_paragraph()
                summary.add_run(
                    f"Found {len(anomaly_rows)} anomal{'y' if len(anomaly_rows) == 1 else 'ies'} on this date.\n"
                ).italic = True
        
        # If no anomalies found at all, add a note
        if not total_anomalies_found:
            no_anomalies = doc.add_paragraph()
            run = no_anomalies.add_run("✓ No cost anomalies detected during this period.")
            run.font.size = Pt(11)
            run.font.color.rgb = RGBColor(0, 128, 0)  # Green color
            run.bold = True
    
    def generate_cost_report(
        self, 
        all_data: Dict, 
        num_days: int,
        anomaly_data: Optional[List[Dict]] = None
    ) -> str:
        """
        Generate a Word document with cost data and optional anomaly detection.
        
        CHANGE: Added optional anomaly_data parameter
        - Backward compatible: If anomaly_data is None, works as before
        - If anomaly_data provided, adds anomaly section at bottom
        
        Args:
            all_data: Dictionary with subscription names as keys
            num_days: Number of days covered in the report
            anomaly_data: Optional list of anomaly detection results (NEW)
        
        Returns:
            Generated filename
        """
        
        doc = Document()
        
        # Add title
        title = doc.add_heading('Azure Cost Summary Report', 0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Create date range string
        end_date = datetime.now() - timedelta(days=1)
        start_date = end_date - timedelta(days=num_days - 1)
        
        # Format dates with day names
        date_list = []
        for i in range(num_days):
            date = start_date + timedelta(days=i)
            date_list.append(f"{date.strftime('%A')} ({date.strftime('%m/%d')})")
        
        date_range_str = ", ".join(date_list)
        
        # Add greeting
        greeting = doc.add_paragraph()
        greeting.add_run("Hi Team,\n\n").bold = False
        
        subscription_text = "subscription" if len(all_data) == 1 else "subscriptions"
        greeting.add_run(
            f"Please find below the Azure cost summary for {date_range_str} "
            f"for {len(all_data)} {subscription_text}, along with percentage changes "
            f"compared to the previous day.\n"
        )
        
        # Add tables for each subscription dynamically
        # Sort subscription names alphabetically for consistent ordering
        sorted_subscriptions = sorted(all_data.keys())
        
        for sub_name in sorted_subscriptions:
            if sub_name in all_data and all_data[sub_name]:
                data = all_data[sub_name]
                
                # Add subscription header
                # Capitalize subscription name for display
                display_name = sub_name.replace('_', ' ').title()
                doc.add_heading(f'{display_name} Subscription', level=2)
                
                # Add cost table
                self.add_table_to_doc(doc, data['cost_table'], data['headers'])
                
                # Add percentage difference table
                self.add_table_to_doc(
                    doc, 
                    data['percent_table'], 
                    data['headers'],
                    f"Percentage difference for {display_name}"
                )
        
        # NEW: Add anomaly detection section if data provided
        if anomaly_data:
            # Get threshold from first result (all use same threshold)
            threshold = anomaly_data[0].get('threshold', 25.0) if anomaly_data else 25.0
            self.add_anomaly_section(doc, anomaly_data, threshold)
        
        # Add closing
        doc.add_paragraph("\nThank you.")
        
        # Save document
        filename = f"Azure_Cost_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
        filepath = os.path.join(self.output_directory, filename)
        doc.save(filepath)
        
        return filename
    
    def prepare_report_data(
        self,
        subscription_id: str,
        subscription_name: str,
        num_days: int,
        cost_data_service,
        cost_processor
    ) -> Dict:
        """
        Prepare data for a subscription report.
        
        UNCHANGED: This method remains the same
        
        Args:
            subscription_id: Azure subscription ID
            subscription_name: Display name for the subscription
            num_days: Number of days to include
            cost_data_service: Service to fetch cost data
            cost_processor: Service to process/categorize costs
        
        Returns:
            Dictionary with cost_table, percent_table, and headers
        """
        
        # Calculate date range
        end_date = datetime.now() - timedelta(days=1)
        start_date = end_date - timedelta(days=num_days - 1)
        
        # Get all data in one API call
        response_data = cost_data_service.get_cost_data_range(
            subscription_id, start_date, end_date
        )
        
        if not response_data:
            return None
        
        daily_data = cost_data_service.parse_range_response(response_data)
        
        # Prepare data structures
        cost_table_data = []
        percent_table_data = []
        all_costs = []
        date_strings = []
        
        # Process each day
        for i in range(num_days - 1, -1, -1):
            date = datetime.now() - timedelta(days=i + 1)
            date_key = int(date.strftime('%Y%m%d'))
            date_str = date.strftime('%m/%d')
            date_strings.append(date_str)
            
            day_rows = daily_data.get(date_key, [])
            costs = cost_processor.process_cost_data(day_rows)
            all_costs.append(costs)
        
        # Determine categories
        categories = cost_processor.get_relevant_categories(all_costs, subscription_name)
        
        # Build cost table
        for i, costs in enumerate(all_costs):
            row = [date_strings[i]]
            for category in categories:
                row.append(f"${costs[category]:.2f}")
            cost_table_data.append(row)
        
        # Build percentage change table
        for i in range(1, len(all_costs)):
            row = [date_strings[i]]
            
            for category in categories:
                prev_cost = all_costs[i - 1][category]
                curr_cost = all_costs[i][category]
                
                percent_change = cost_processor.calculate_percentage_change(
                    prev_cost, curr_cost
                )
                
                row.append(f"{percent_change:+.2f}%")
            
            percent_table_data.append(row)
        
        headers = ['Date'] + categories
        
        return {
            'cost_table': cost_table_data,
            'percent_table': percent_table_data,
            'headers': headers,
            'date_strings': date_strings
        }