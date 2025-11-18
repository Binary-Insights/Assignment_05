"""
LLM-based extraction and value mapping for Agentic RAG.
Chains multiple LLM calls to intelligently extract values from search results.
"""

import json
import logging
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser, PydanticOutputParser

logger = logging.getLogger(__name__)


# ===========================
# Pydantic Models for Structured Extraction
# ===========================

class SearchContext(BaseModel):
    """Context about what we're searching for."""
    field_name: str = Field(description="Name of the field to fill")
    entity_type: str = Field(description="Type of entity (e.g., company_record)")
    company_name: str = Field(description="Name of the company")
    current_value: Optional[str] = Field(None, description="Current value in payload (if any)")
    importance: str = Field(description="Importance level: critical, high, medium, low")


class SearchResult(BaseModel):
    """A single search result from Tavily."""
    title: str = Field(description="Title of the result")
    content: str = Field(description="Content/body of the result")
    url: str = Field(description="Source URL")
    relevance_score: float = Field(0.0, description="Relevance to query (0-1)")


class ExtractionQuestion(BaseModel):
    """Question to ask LLM about extracting field value."""
    question: str = Field(description="The extraction question")
    context_field: str = Field(description="Field being extracted")
    company_name: str = Field(description="Company name for context")
    expected_format: str = Field(description="Expected format of answer (e.g., 'year', 'city', 'text')")


class ExtractedValue(BaseModel):
    """Extracted and validated value for a field."""
    field_name: str = Field(description="Field name")
    extracted_value: Optional[Any] = Field(None, description="Extracted value (can be string, list, dict, etc.)")
    confidence: float = Field(0.0, description="Confidence score (0-1)")
    reasoning: str = Field(description="Why this value was selected")
    sources: List[str] = Field(default_factory=list, description="URLs that support this value")
    extracted_at: str = Field(description="ISO timestamp of extraction")


class ChainedExtractionResult(BaseModel):
    """Final result of chained extraction process."""
    field_name: str = Field(description="Field being extracted")
    final_value: Optional[str] = Field(None, description="Final value to fill in payload")
    confidence: float = Field(0.0, description="Overall confidence (0-1)")
    chain_steps: List[str] = Field(default_factory=list, description="Steps in extraction chain")
    reasoning: str = Field(description="Full reasoning for final decision")
    sources: List[str] = Field(default_factory=list, description="Supporting sources")


# ===========================
# LLM Extraction Chain
# ===========================

class LLMExtractionChain:
    """Chains multiple LLM calls to extract and validate field values."""
    
    def __init__(self, llm_model: str = "gpt-4o-mini", temperature: float = 0.1):
        """
        Initialize the extraction chain.
        
        Args:
            llm_model: LLM model to use
            temperature: Temperature for LLM (lower = more deterministic). Default 0.1 for high consistency.
        """
        self.llm = ChatOpenAI(model=llm_model, temperature=temperature)
        self.json_parser = JsonOutputParser()
        self.pydantic_parser = PydanticOutputParser(pydantic_object=ExtractedValue)
        logger.info(f"🔗 [EXTRACTION CHAIN] Initialized with model: {llm_model}")
    
    async def generate_extraction_question(
        self,
        field_name: str,
        entity_type: str,
        company_name: str,
        importance: str
    ) -> ExtractionQuestion:
        """
        Step 1: Generate a targeted question for extraction using pipe operator.
        
        Args:
            field_name: Field to extract
            entity_type: Type of entity
            company_name: Company name
            importance: Importance level
        
        Returns:
            ExtractionQuestion with targeted question
        """
        logger.info(f"🔗 [CHAIN STEP 1] Generating extraction question for {field_name}")
        
        prompt = ChatPromptTemplate.from_template("""You are an expert data extraction specialist. 
Generate a precise, targeted question to extract a specific field value.
The question should be clear and specific about what information is needed.

Generate an extraction question for:
- Field Name: {field_name}
- Entity Type: {entity_type}
- Company: {company_name}
- Importance: {importance}

Respond with ONLY valid JSON (no additional text):
{{
  "question": "The extraction question",
  "expected_format": "The expected format of the answer",
  "context": "Brief context about why this field matters"
}}""")
        
        try:
            # Use pipe operator for proper chaining
            chain = prompt | self.llm | JsonOutputParser()
            response = await chain.ainvoke({
                "field_name": field_name,
                "entity_type": entity_type,
                "company_name": company_name,
                "importance": importance
            })
            
            question = ExtractionQuestion(
                question=response.get("question", f"What is the {field_name}?"),
                context_field=field_name,
                company_name=company_name,
                expected_format=response.get("expected_format", "string")
            )
            
            logger.info(f"✅ [CHAIN STEP 1] Generated question: {question.question}")
            return question
            
        except Exception as e:
            logger.error(f"❌ [CHAIN STEP 1] Error: {e}")
            return ExtractionQuestion(
                question=f"What is the {field_name} for {company_name}?",
                context_field=field_name,
                company_name=company_name,
                expected_format="string"
            )
    
    async def extract_value_from_context(
        self,
        question: ExtractionQuestion,
        search_results: List[Dict[str, Any]],
        company_name: str
    ) -> ExtractedValue:
        """
        Step 2: Extract value from search results using LLM with pipe operator.
        
        Args:
            question: ExtractionQuestion from step 1
            search_results: List of Tavily search results
            company_name: Company name
        
        Returns:
            ExtractedValue with extracted information
        """
        logger.info(f"🔗 [CHAIN STEP 2] Extracting value from {len(search_results)} search results")
        
        # Prepare search results context
        results_context = "\n\n".join([
            f"Source {i+1}: {result.get('title', 'N/A')}\n"
            f"URL: {result.get('url', 'N/A')}\n"
            f"Content: {result.get('content', '')[:500]}"
            for i, result in enumerate(search_results[:5])  # Top 5 results
        ])
        
        prompt = ChatPromptTemplate.from_template("""You are an expert data extraction specialist.
Extract specific information from search results with high accuracy.
Be conservative - only extract values you're confident about.
Always provide reasoning for your extraction.

Question: {question}

Expected Format: {expected_format}
Company: {company_name}
Field: {field_name}

Search Results:
{results_context}

Extract the {field_name} value from these results.
Respond with ONLY valid JSON (no additional text):
{{
  "field_name": "{field_name}",
  "extracted_value": "<the extracted value or null if not found>",
  "confidence": <0.0-1.0>,
  "reasoning": "<why you chose this value>",
  "sources": ["<url1>", "<url2>"]
}}""")
        
        try:
            # Use pipe operator for proper chaining
            chain = prompt | self.llm | JsonOutputParser()
            response = await chain.ainvoke({
                "question": question.question,
                "expected_format": question.expected_format,
                "company_name": company_name,
                "field_name": question.context_field,
                "results_context": results_context
            })
            
            extracted = ExtractedValue(
                field_name=question.context_field,
                extracted_value=response.get("extracted_value"),
                confidence=float(response.get("confidence", 0.0)),
                reasoning=response.get("reasoning", ""),
                sources=response.get("sources", []),
                extracted_at=datetime.utcnow().isoformat()
            )
            
            logger.info(f"✅ [CHAIN STEP 2] Extracted: {extracted.extracted_value} (confidence: {extracted.confidence})")
            return extracted
            
        except Exception as e:
            logger.error(f"❌ [CHAIN STEP 2] Error: {e}")
            return ExtractedValue(
                field_name=question.context_field,
                extracted_value=None,
                confidence=0.0,
                reasoning=f"Extraction failed: {str(e)}",
                sources=[],
                extracted_at=datetime.utcnow().isoformat()
            )
    
    async def validate_and_refine(
        self,
        extracted: ExtractedValue,
        field_name: str,
        company_name: str,
        importance: str
    ) -> ExtractedValue:
        """
        Step 3: Validate and refine extracted value using pipe operator.
        
        Args:
            extracted: Previously extracted value
            field_name: Field being validated
            company_name: Company name
            importance: Importance level
        
        Returns:
            Refined ExtractedValue
        """
        logger.info(f"🔗 [CHAIN STEP 3] Validating extracted value: {extracted.extracted_value}")
        
        if extracted.extracted_value is None:
            logger.info(f"⏭️  [CHAIN STEP 3] No value extracted, returning as-is")
            return extracted
        
        prompt = ChatPromptTemplate.from_template("""You are an expert data validator.
Validate and refine extracted information.
Ensure consistency and correctness.

Validate this extracted value:

Company: {company_name}
Field: {field_name}
Extracted Value: {extracted_value}
Current Confidence: {confidence}
Reasoning: {reasoning}
Sources: {sources}
Importance: {importance}

Respond with ONLY valid JSON (no additional text):
{{
  "is_valid": <true/false>,
  "refined_value": "<refined value or null>",
  "final_confidence": <0.0-1.0>,
  "validation_notes": "<any validation notes>"
}}""")
        
        try:
            # Use pipe operator for proper chaining
            chain = prompt | self.llm | JsonOutputParser()
            response = await chain.ainvoke({
                "company_name": company_name,
                "field_name": field_name,
                "extracted_value": extracted.extracted_value,
                "confidence": extracted.confidence,
                "reasoning": extracted.reasoning,
                "sources": ", ".join(extracted.sources),
                "importance": importance
            })
            
            if response.get("is_valid"):
                refined = ExtractedValue(
                    field_name=extracted.field_name,
                    extracted_value=response.get("refined_value", extracted.extracted_value),
                    confidence=float(response.get("final_confidence", extracted.confidence)),
                    reasoning=f"{extracted.reasoning} [Validated: {response.get('validation_notes', '')}]",
                    sources=extracted.sources,
                    extracted_at=extracted.extracted_at
                )
                logger.info(f"✅ [CHAIN STEP 3] Value validated and refined")
                return refined
            else:
                logger.warning(f"⚠️  [CHAIN STEP 3] Value failed validation")
                extracted.confidence = 0.0
                return extracted
                
        except Exception as e:
            logger.error(f"❌ [CHAIN STEP 3] Validation error: {e}")
            return extracted
    
    async def run_extraction_chain(
        self,
        field_name: str,
        entity_type: str,
        company_name: str,
        importance: str,
        search_results: List[Dict[str, Any]]
    ) -> ChainedExtractionResult:
        """
        Run the complete extraction chain.
        
        Args:
            field_name: Field to extract
            entity_type: Entity type
            company_name: Company name
            importance: Importance level
            search_results: Tavily search results
        
        Returns:
            ChainedExtractionResult with final value
        """
        logger.info(f"\n🔗 [EXTRACTION CHAIN] Starting chain for {field_name}")
        chain_steps = []
        
        # Step 1: Generate question
        question = await self.generate_extraction_question(
            field_name, entity_type, company_name, importance
        )
        chain_steps.append(f"Generated question: {question.question}")
        
        # Step 2: Extract from context
        extracted = await self.extract_value_from_context(
            question, search_results, company_name
        )
        chain_steps.append(f"Extracted value: {extracted.extracted_value} (confidence: {extracted.confidence})")
        
        # Step 3: Validate and refine
        refined = await self.validate_and_refine(
            extracted, field_name, company_name, importance
        )
        chain_steps.append(f"Validated value: {refined.extracted_value} (confidence: {refined.confidence})")
        
        # Final result
        result = ChainedExtractionResult(
            field_name=field_name,
            final_value=refined.extracted_value if refined.confidence >= 0.5 else None,
            confidence=refined.confidence,
            chain_steps=chain_steps,
            reasoning=refined.reasoning,
            sources=refined.sources
        )
        
        logger.info(f"✅ [EXTRACTION CHAIN] Complete: {result.final_value} (confidence: {result.confidence})")
        return result


# ===========================
# Utility Functions
# ===========================

async def extract_field_value(
    field_name: str,
    entity_type: str,
    company_name: str,
    importance: str,
    search_results: List[Dict[str, Any]],
    llm_model: str = "gpt-4o-mini"
) -> ChainedExtractionResult:
    """
    Convenience function to run extraction chain for a single field.
    
    Args:
        field_name: Field to extract
        entity_type: Entity type
        company_name: Company name
        importance: Importance level
        search_results: Tavily search results
        llm_model: LLM model to use
    
    Returns:
        ChainedExtractionResult
    """
    chain = LLMExtractionChain(llm_model=llm_model)
    return await chain.run_extraction_chain(
        field_name, entity_type, company_name, importance, search_results
    )
