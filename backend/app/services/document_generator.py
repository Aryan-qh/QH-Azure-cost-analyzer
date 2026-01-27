"""
Word Document Generation Service - SIMPLIFIED VERSION

CHANGE: Refactored to generate simple summary reports
- Removed detailed resource breakdown (moved to Excel)
- Removed anomaly detection section (moved to Excel)
- Now creates email-friendly summaries with only subscription totals

PURPOSE:
Generate simple Word documents showing:
1. Daily total costs per subscription
2. Period summary with grand total
3. Reference to Excel file for details

Logic:
- Single table with Date | Subscription1 | Subscription2 | ... | Total
- Clean, concise format suitable for email
- Detailed analysis moved to Excel file
"""
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from datetime import datetime, timedelta
from typing import Dict, List
import os


class DocumentGeneratorService:
    """Generate simple Word documents for cost report summaries"""
    
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
    
    def generate_cost_report(
        self, 
        all_data: Dict, 
        num_days: int
    ) -> str:
        """
        Generate a SIMPLIFIED Word document with only subscription totals.
        
        CHANGE: Removed detailed resource breakdown and anomalies
        - Now shows only total cost per subscription per day
        - Detailed breakdown moved to Excel file
        - Designed for email-friendly summary
        
        Args:
            all_data: Dictionary with subscription names as keys
            num_days: Number of days covered in the report
        
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
            f"for {len(all_data)} {subscription_text}.\n\n"
            f"For detailed resource breakdown and anomaly detection, please refer to the accompanying Excel file.\n"
        )
        
        # Create single summary table with all subscriptions
        # Sort subscription names alphabetically for consistent ordering
        sorted_subscriptions = sorted(all_data.keys())
        
        # Build table: Date | Subscription1 | Subscription2 | ... | Total
        table_headers = ['Date'] + [sub.replace('_', ' ').title() for sub in sorted_subscriptions] + ['Total']
        table_data = []
        
        # Extract totals for each day
        for day_idx in range(num_days):
            row = []
            
            # Date (from first subscription's data)
            first_sub = sorted_subscriptions[0]
            if day_idx < len(all_data[first_sub]['cost_table']):
                date_str = all_data[first_sub]['cost_table'][day_idx][0]
                row.append(date_str)
            else:
                continue
            
            # Each subscription's total for this day
            day_total = 0.0
            for sub_name in sorted_subscriptions:
                if sub_name in all_data and all_data[sub_name]:
                    data = all_data[sub_name]
                    if day_idx < len(data['cost_table']):
                        cost_row = data['cost_table'][day_idx]
                        # Last value in cost_table is the total
                        total_str = cost_row[-1]
                        row.append(total_str)
                        # Add to day total (remove $ and commas)
                        day_total += float(total_str.replace('$', '').replace(',', ''))
                    else:
                        row.append('$0.00')
                else:
                    row.append('$0.00')
            
            # Add day total
            row.append(f'${day_total:,.2f}')
            table_data.append(row)
        
        # Add the table
        self.add_table_to_doc(doc, table_data, table_headers, "Daily Total Costs by Subscription")
        
        # Add period summary
        doc.add_paragraph()
        summary_para = doc.add_paragraph()
        summary_para.add_run("Period Summary:\n").bold = True
        
        # Calculate totals for each subscription
        for sub_name in sorted_subscriptions:
            if sub_name in all_data and all_data[sub_name]:
                data = all_data[sub_name]
                sub_total = 0.0
                
                for cost_row in data['cost_table']:
                    total_str = cost_row[-1]
                    sub_total += float(total_str.replace('$', '').replace(',', ''))
                
                display_name = sub_name.replace('_', ' ').title()
                summary_para.add_run(f"• {display_name}: ${sub_total:,.2f}\n")
        
        # Grand total
        grand_total = 0.0
        for sub_name in sorted_subscriptions:
            if sub_name in all_data and all_data[sub_name]:
                data = all_data[sub_name]
                for cost_row in data['cost_table']:
                    total_str = cost_row[-1]
                    grand_total += float(total_str.replace('$', '').replace(',', ''))
        
        summary_para.add_run(f"\nGrand Total: ${grand_total:,.2f}").bold = True
        
        # Add closing
        doc.add_paragraph("\nFor detailed analysis, please see the attached Excel file.")
        doc.add_paragraph("\nThank you.")
        
        # Save document
        filename = f"Azure_Cost_Summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
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
        
        UNCHANGED: This method remains the same - still needed to gather cost data
        
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