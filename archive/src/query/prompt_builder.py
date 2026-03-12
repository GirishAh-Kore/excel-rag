"""
Prompt builder for generating structured prompts for LLM-based answer generation.

This module creates prompts for different types of queries including single value
answers, tables, comparisons, and formula explanations. Supports multi-language
prompts (English and Thai).
"""

from typing import Any, Dict, List, Optional
from enum import Enum

from src.models.domain_models import RetrievedData, DataType


class AnswerType(str, Enum):
    """Types of answers that can be generated."""
    SINGLE_VALUE = "single_value"
    TABLE = "table"
    COMPARISON = "comparison"
    FORMULA = "formula"
    LIST = "list"
    GENERAL = "general"


class Language(str, Enum):
    """Supported languages for prompts."""
    ENGLISH = "en"
    THAI = "th"


class PromptBuilder:
    """
    Builds structured prompts for LLM-based answer generation.
    
    Creates prompts with clear instructions, context, and formatting guidelines
    tailored to different answer types and languages.
    """
    
    def __init__(self):
        """Initialize the prompt builder."""
        pass
    
    def build_answer_prompt(
        self,
        query: str,
        retrieved_data: List[RetrievedData],
        answer_type: AnswerType = AnswerType.GENERAL,
        language: Language = Language.ENGLISH,
        additional_context: Optional[str] = None
    ) -> str:
        """
        Build a prompt for generating an answer to a query.
        
        Args:
            query: The user's question
            retrieved_data: Data retrieved from Excel files
            answer_type: Type of answer to generate
            language: Language for the prompt and answer
            additional_context: Optional additional context
            
        Returns:
            Formatted prompt ready for LLM generation
        """
        # Format the retrieved data
        formatted_data = self._format_retrieved_data(retrieved_data)
        
        # Get the appropriate system prompt
        system_instructions = self._get_system_instructions(answer_type, language)
        
        # Get answer-type specific guidelines
        guidelines = self._get_answer_guidelines(answer_type, language)
        
        # Build the complete prompt
        prompt_parts = [
            system_instructions,
            "",
            f"**Question:** {query}",
            "",
            "**Retrieved Data:**",
            formatted_data,
        ]
        
        if additional_context:
            prompt_parts.extend([
                "",
                f"**Additional Context:** {additional_context}",
            ])
        
        prompt_parts.extend([
            "",
            "**Instructions:**",
            guidelines,
            "",
            "**Answer:**"
        ])
        
        return "\n".join(prompt_parts)
    
    def build_formula_explanation_prompt(
        self,
        formula: str,
        cell_range: str,
        sheet_name: str,
        file_name: str,
        language: Language = Language.ENGLISH
    ) -> str:
        """
        Build a prompt for explaining an Excel formula.
        
        Args:
            formula: The Excel formula to explain
            cell_range: Cell range containing the formula
            sheet_name: Sheet name
            file_name: File name
            language: Language for the explanation
            
        Returns:
            Formatted prompt for formula explanation
        """
        if language == Language.THAI:
            return f"""คุณเป็นผู้เชี่ยวชาญด้าน Excel ที่อธิบายสูตรให้เข้าใจง่าย

**สูตร:** {formula}
**ตำแหน่ง:** {file_name}, Sheet: {sheet_name}, Cell: {cell_range}

**คำแนะนำ:**
1. อธิบายว่าสูตรนี้ทำอะไร
2. แยกย่อยส่วนประกอบของสูตร
3. อธิบายฟังก์ชันที่ใช้
4. ให้ตัวอย่างการคำนวณถ้าเป็นไปได้
5. ใช้ภาษาที่เข้าใจง่าย

**คำอธิบาย:**"""
        else:
            return f"""You are an Excel expert who explains formulas in simple terms.

**Formula:** {formula}
**Location:** {file_name}, Sheet: {sheet_name}, Cell: {cell_range}

**Instructions:**
1. Explain what this formula does
2. Break down the formula components
3. Explain the functions used
4. Provide a calculation example if possible
5. Use simple, clear language

**Explanation:**"""
    
    def build_comparison_prompt(
        self,
        query: str,
        comparison_data: Dict[str, Any],
        files_compared: List[str],
        language: Language = Language.ENGLISH
    ) -> str:
        """
        Build a prompt for generating a comparison answer.
        
        Args:
            query: The user's comparison question
            comparison_data: Aligned and calculated comparison data
            files_compared: List of file names being compared
            language: Language for the answer
            
        Returns:
            Formatted prompt for comparison answer
        """
        files_list = ", ".join(files_compared)
        formatted_comparison = self._format_comparison_data(comparison_data)
        
        if language == Language.THAI:
            return f"""คุณกำลังตอบคำถามเปรียบเทียบข้อมูลจากไฟล์ Excel หลายไฟล์

**คำถาม:** {query}

**ไฟล์ที่เปรียบเทียบ:** {files_list}

**ข้อมูลเปรียบเทียบ:**
{formatted_comparison}

**คำแนะนำ:**
1. สรุปความแตกต่างหลักที่พบ
2. ระบุตัวเลขที่สำคัญและการเปลี่ยนแปลง
3. ชี้ให้เห็นแนวโน้ม (เพิ่มขึ้น, ลดลง, คงที่)
4. ใช้ตัวเลขจากข้อมูลที่ให้มา
5. อ้างอิงแหล่งที่มาของข้อมูล
6. ตอบโดยตรงและชัดเจน

**คำตอบ:**"""
        else:
            return f"""You are answering a comparison question based on data from multiple Excel files.

**Question:** {query}

**Files Compared:** {files_list}

**Comparison Data:**
{formatted_comparison}

**Instructions:**
1. Summarize the key differences found
2. Highlight important numbers and changes
3. Point out trends (increasing, decreasing, stable)
4. Use exact numbers from the provided data
5. Cite the sources of the data
6. Answer directly and clearly

**Answer:**"""
    
    def _get_system_instructions(self, answer_type: AnswerType, language: Language) -> str:
        """Get system-level instructions based on answer type and language."""
        if language == Language.THAI:
            base = "คุณเป็นผู้ช่วยที่ตอบคำถามจากข้อมูลในไฟล์ Excel"
            
            type_specific = {
                AnswerType.SINGLE_VALUE: "คุณให้คำตอบที่เฉพาะเจาะจงและตรงประเด็น",
                AnswerType.TABLE: "คุณนำเสนอข้อมูลในรูปแบบตารางที่อ่านง่าย",
                AnswerType.COMPARISON: "คุณเปรียบเทียบข้อมูลจากหลายแหล่งและสรุปความแตกต่าง",
                AnswerType.FORMULA: "คุณอธิบายสูตร Excel ให้เข้าใจง่าย",
                AnswerType.LIST: "คุณนำเสนอข้อมูลในรูปแบบรายการ",
                AnswerType.GENERAL: "คุณให้ข้อมูลที่ครบถ้วนและเป็นประโยชน์"
            }
            
            return f"{base}. {type_specific.get(answer_type, type_specific[AnswerType.GENERAL])}"
        else:
            base = "You are an assistant that answers questions based on data from Excel files"
            
            type_specific = {
                AnswerType.SINGLE_VALUE: "You provide specific, direct answers",
                AnswerType.TABLE: "You present data in clear, readable table format",
                AnswerType.COMPARISON: "You compare data from multiple sources and summarize differences",
                AnswerType.FORMULA: "You explain Excel formulas in simple terms",
                AnswerType.LIST: "You present data in list format",
                AnswerType.GENERAL: "You provide comprehensive and helpful information"
            }
            
            return f"{base}. {type_specific.get(answer_type, type_specific[AnswerType.GENERAL])}"
    
    def _get_answer_guidelines(self, answer_type: AnswerType, language: Language) -> str:
        """Get answer-specific guidelines based on type and language."""
        if language == Language.THAI:
            guidelines = {
                AnswerType.SINGLE_VALUE: """1. ตอบคำถามโดยตรงด้วยค่าที่ถูกต้อง
2. ใช้การจัดรูปแบบตัวเลขตามต้นฉบับ (สกุลเงิน, เปอร์เซ็นต์)
3. ระบุแหล่งที่มา (ไฟล์, ชีต, เซลล์)
4. ให้คำตอบสั้นและชัดเจน (1-2 ประโยค)""",
                
                AnswerType.TABLE: """1. นำเสนอข้อมูลในรูปแบบตาราง Markdown
2. จัดแนวคอลัมน์ให้เรียบร้อย
3. รวมหัวตารางที่ชัดเจน
4. จำกัดแถวไม่เกิน 20 แถว (แสดงตัวอย่างถ้ามีมากกว่า)
5. ระบุแหล่งที่มาด้านล่างตาราง""",
                
                AnswerType.COMPARISON: """1. เริ่มด้วยสรุปความแตกต่างหลัก
2. ระบุตัวเลขที่เฉพาะเจาะจง (ค่าสัมบูรณ์และเปอร์เซ็นต์)
3. ชี้ให้เห็นแนวโน้มและรูปแบบ
4. เปรียบเทียบแต่ละไฟล์อย่างชัดเจน
5. ระบุแหล่งที่มาสำหรับแต่ละค่า""",
                
                AnswerType.FORMULA: """1. อธิบายวัตถุประสงค์ของสูตร
2. แยกย่อยส่วนประกอบ
3. อธิบายฟังก์ชันที่ใช้
4. ให้ตัวอย่างการคำนวณ
5. ใช้ภาษาที่เข้าใจง่าย""",
                
                AnswerType.LIST: """1. นำเสนอรายการด้วยจุดหรือตัวเลข
2. จัดเรียงตามลำดับที่เหมาะสม
3. ให้บริบทสำหรับแต่ละรายการ
4. จำกัดไม่เกิน 15 รายการ
5. ระบุแหล่งที่มา""",
                
                AnswerType.GENERAL: """1. ตอบคำถามโดยตรงและชัดเจน
2. ใช้ตัวเลขที่แน่นอนจากข้อมูล
3. รักษาการจัดรูปแบบตามต้นฉบับ
4. ระบุแหล่งที่มา (ไฟล์, ชีต, ช่วงเซลล์)
5. ถ้าข้อมูลไม่สมบูรณ์ ให้ระบุข้อจำกัด
6. ให้คำตอบกระชับ (ไม่เกิน 200 คำ)"""
            }
        else:
            guidelines = {
                AnswerType.SINGLE_VALUE: """1. Answer the question directly with the exact value
2. Use original Excel formatting (currency, percentage)
3. Cite the source (file, sheet, cell)
4. Keep the answer brief and clear (1-2 sentences)""",
                
                AnswerType.TABLE: """1. Present data in Markdown table format
2. Align columns properly
3. Include clear column headers
4. Limit to 20 rows maximum (show sample if more)
5. Cite the source below the table""",
                
                AnswerType.COMPARISON: """1. Start with a summary of key differences
2. Provide specific numbers (absolute and percentage)
3. Highlight trends and patterns
4. Compare each file clearly
5. Cite sources for each value""",
                
                AnswerType.FORMULA: """1. Explain the formula's purpose
2. Break down the components
3. Explain functions used
4. Provide a calculation example
5. Use simple, clear language""",
                
                AnswerType.LIST: """1. Present items with bullets or numbers
2. Order logically
3. Provide context for each item
4. Limit to 15 items maximum
5. Cite sources""",
                
                AnswerType.GENERAL: """1. Answer the question directly and clearly
2. Use exact numbers from the data
3. Preserve original formatting (currency, dates, percentages)
4. Cite sources (file, sheet, cell range)
5. If data is incomplete, acknowledge limitations
6. Keep answer concise (under 200 words)"""
            }
        
        return guidelines.get(answer_type, guidelines[AnswerType.GENERAL])
    
    def _format_retrieved_data(self, retrieved_data: List[RetrievedData]) -> str:
        """Format retrieved data for inclusion in prompt."""
        if not retrieved_data:
            return "No data retrieved."
        
        formatted_parts = []
        for i, data in enumerate(retrieved_data, 1):
            parts = [
                f"**Source {i}:**",
                f"- File: {data.file_name}",
                f"- Sheet: {data.sheet_name}",
                f"- Cell Range: {data.cell_range}",
                f"- Data Type: {data.data_type.value}",
            ]
            
            if data.original_format:
                parts.append(f"- Format: {data.original_format}")
            
            # Format the data value
            data_str = self._format_data_value(data.data, data.data_type, data.original_format)
            parts.append(f"- Value: {data_str}")
            
            formatted_parts.append("\n".join(parts))
        
        return "\n\n".join(formatted_parts)
    
    def _format_data_value(
        self,
        value: Any,
        data_type: DataType,
        original_format: Optional[str]
    ) -> str:
        """Format a data value for display in prompt."""
        if value is None:
            return "None"
        
        # Handle different data types
        if data_type == DataType.NUMBER:
            if original_format:
                # Indicate the format should be preserved
                return f"{value} (format: {original_format})"
            return str(value)
        
        elif data_type == DataType.DATE:
            return str(value)
        
        elif data_type == DataType.FORMULA:
            return f"Formula result: {value}"
        
        elif isinstance(value, list):
            # Handle table data
            if len(value) > 10:
                return f"Table with {len(value)} rows (showing first 10):\n{self._format_table_preview(value[:10])}"
            return f"Table with {len(value)} rows:\n{self._format_table_preview(value)}"
        
        elif isinstance(value, dict):
            # Handle dictionary data
            return self._format_dict_preview(value)
        
        else:
            return str(value)
    
    def _format_table_preview(self, rows: List[Dict[str, Any]]) -> str:
        """Format a table preview for the prompt."""
        if not rows:
            return "Empty table"
        
        # Get headers from first row
        headers = list(rows[0].keys())
        
        # Create simple text table
        lines = [" | ".join(headers)]
        lines.append("-" * len(lines[0]))
        
        for row in rows:
            values = [str(row.get(h, "")) for h in headers]
            lines.append(" | ".join(values))
        
        return "\n".join(lines)
    
    def _format_dict_preview(self, data: Dict[str, Any]) -> str:
        """Format a dictionary preview for the prompt."""
        lines = []
        for key, value in data.items():
            if isinstance(value, (list, dict)):
                lines.append(f"  {key}: {type(value).__name__} with {len(value)} items")
            else:
                lines.append(f"  {key}: {value}")
        return "\n".join(lines)
    
    def _format_comparison_data(self, comparison_data: Dict[str, Any]) -> str:
        """Format comparison data for the prompt."""
        if not comparison_data:
            return "No comparison data available."
        
        lines = []
        
        # Format aligned data
        if "aligned_data" in comparison_data:
            lines.append("**Aligned Data:**")
            aligned = comparison_data["aligned_data"]
            if isinstance(aligned, dict):
                for key, value in aligned.items():
                    lines.append(f"  {key}: {value}")
            else:
                lines.append(f"  {aligned}")
            lines.append("")
        
        # Format differences
        if "differences" in comparison_data:
            lines.append("**Differences:**")
            diffs = comparison_data["differences"]
            if isinstance(diffs, dict):
                for metric, diff_data in diffs.items():
                    if isinstance(diff_data, dict):
                        lines.append(f"  {metric}:")
                        for key, value in diff_data.items():
                            lines.append(f"    {key}: {value}")
                    else:
                        lines.append(f"  {metric}: {diff_data}")
            else:
                lines.append(f"  {diffs}")
            lines.append("")
        
        # Format summary if available
        if "summary" in comparison_data:
            lines.append(f"**Summary:** {comparison_data['summary']}")
        
        return "\n".join(lines) if lines else "No comparison data available."
    
    def detect_language(self, text: str) -> Language:
        """
        Detect the language of the input text.
        
        Args:
            text: Text to analyze
            
        Returns:
            Detected language
        """
        # Simple heuristic: check for Thai characters
        thai_chars = sum(1 for c in text if '\u0E00' <= c <= '\u0E7F')
        total_chars = sum(1 for c in text if c.isalpha())
        
        if total_chars > 0 and thai_chars / total_chars > 0.3:
            return Language.THAI
        
        return Language.ENGLISH
    
    def infer_answer_type(
        self,
        query: str,
        retrieved_data: List[RetrievedData]
    ) -> AnswerType:
        """
        Infer the appropriate answer type based on query and data.
        
        Args:
            query: The user's question
            retrieved_data: Retrieved data
            
        Returns:
            Inferred answer type
        """
        query_lower = query.lower()
        
        # Check for formula-related queries
        if any(word in query_lower for word in ["formula", "calculate", "calculation", "สูตร", "คำนวณ"]):
            return AnswerType.FORMULA
        
        # Check for comparison queries
        if any(word in query_lower for word in ["compare", "difference", "vs", "versus", "between", "เปรียบเทียบ", "ต่าง"]):
            return AnswerType.COMPARISON
        
        # Check for list queries
        if any(word in query_lower for word in ["list", "all", "show me", "รายการ", "ทั้งหมด"]):
            return AnswerType.LIST
        
        # Check data structure
        if retrieved_data:
            first_data = retrieved_data[0].data
            
            # If data is a list/table
            if isinstance(first_data, list) and len(first_data) > 1:
                return AnswerType.TABLE
            
            # If single value
            if not isinstance(first_data, (list, dict)):
                return AnswerType.SINGLE_VALUE
        
        return AnswerType.GENERAL
