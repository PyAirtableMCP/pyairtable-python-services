"""
Quality assurance and validation service for LLM analysis results
"""
import re
import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from .table_analysis import AnalysisResult, AnalysisCategory

logger = logging.getLogger(__name__)


class ValidationResult(str, Enum):
    """Validation result types"""
    VALID = "valid"
    WARNING = "warning"
    INVALID = "invalid"


@dataclass
class QualityCheck:
    """Quality check result"""
    check_name: str
    result: ValidationResult
    score: float  # 0-1
    message: str
    suggestions: List[str]


class QualityAssuranceService:
    """Service for validating and improving LLM analysis results"""
    
    def __init__(self):
        self.min_confidence_threshold = 0.5
        self.min_description_length = 20
        self.min_recommendation_length = 30
        self.required_implementation_steps = 1
        
        # Common patterns for validation
        self.priority_patterns = ["high", "medium", "low"]
        self.effort_patterns = ["low", "medium", "high"]
        
        # Quality scoring weights
        self.quality_weights = {
            "confidence_score": 0.3,
            "content_quality": 0.25,
            "actionability": 0.2,
            "specificity": 0.15,
            "consistency": 0.1
        }
    
    def validate_analysis_result(self, result: AnalysisResult) -> List[QualityCheck]:
        """
        Comprehensive validation of a single analysis result
        
        Args:
            result: Analysis result to validate
            
        Returns:
            List of quality checks performed
        """
        checks = []
        
        # 1. Confidence score validation
        checks.append(self._validate_confidence_score(result))
        
        # 2. Content quality validation
        checks.append(self._validate_content_quality(result))
        
        # 3. Actionability validation
        checks.append(self._validate_actionability(result))
        
        # 4. Specificity validation
        checks.append(self._validate_specificity(result))
        
        # 5. Consistency validation
        checks.append(self._validate_consistency(result))
        
        # 6. Category alignment validation
        checks.append(self._validate_category_alignment(result))
        
        return checks
    
    def validate_batch_results(
        self, 
        results: Dict[str, Dict[str, List[AnalysisResult]]]
    ) -> Dict[str, Any]:
        """
        Validate batch analysis results
        
        Args:
            results: Batch results to validate
            
        Returns:
            Validation summary with scores and recommendations
        """
        validation_summary = {
            "overall_quality_score": 0.0,
            "table_scores": {},
            "category_scores": {},
            "quality_issues": [],
            "recommendations": [],
            "filtered_results": {},
            "statistics": {
                "total_analyses": 0,
                "valid_analyses": 0,
                "warning_analyses": 0,
                "invalid_analyses": 0
            }
        }
        
        all_scores = []
        category_scores = {cat.value: [] for cat in AnalysisCategory}
        
        for table_id, table_results in results.items():
            table_quality_checks = []
            table_filtered_results = {}
            
            for category, analysis_list in table_results.items():
                category_filtered = []
                
                for analysis in analysis_list:
                    validation_summary["statistics"]["total_analyses"] += 1
                    
                    # Validate individual result
                    quality_checks = self.validate_analysis_result(analysis)
                    table_quality_checks.extend(quality_checks)
                    
                    # Calculate overall quality score for this result
                    result_score = self._calculate_result_quality_score(quality_checks)
                    all_scores.append(result_score)
                    category_scores[category].append(result_score)
                    
                    # Categorize by validation result
                    worst_check = min(quality_checks, key=lambda c: c.score)
                    if worst_check.result == ValidationResult.VALID:
                        validation_summary["statistics"]["valid_analyses"] += 1
                        category_filtered.append(analysis)
                    elif worst_check.result == ValidationResult.WARNING:
                        validation_summary["statistics"]["warning_analyses"] += 1
                        # Include with warning flag
                        analysis_dict = analysis.to_dict()
                        analysis_dict["quality_warning"] = worst_check.message
                        category_filtered.append(analysis)
                    else:
                        validation_summary["statistics"]["invalid_analyses"] += 1
                        validation_summary["quality_issues"].append({
                            "table_id": table_id,
                            "category": category,
                            "issue": worst_check.message,
                            "analysis_preview": analysis.description[:100]
                        })
                
                if category_filtered:
                    table_filtered_results[category] = category_filtered
            
            # Calculate table quality score
            if table_quality_checks:
                table_score = sum(c.score for c in table_quality_checks) / len(table_quality_checks)
                validation_summary["table_scores"][table_id] = table_score
            
            validation_summary["filtered_results"][table_id] = table_filtered_results
        
        # Calculate overall scores
        if all_scores:
            validation_summary["overall_quality_score"] = sum(all_scores) / len(all_scores)
        
        # Calculate category scores
        for category, scores in category_scores.items():
            if scores:
                validation_summary["category_scores"][category] = sum(scores) / len(scores)
        
        # Generate recommendations
        validation_summary["recommendations"] = self._generate_quality_recommendations(
            validation_summary
        )
        
        return validation_summary
    
    def _validate_confidence_score(self, result: AnalysisResult) -> QualityCheck:
        """Validate confidence score"""
        score = result.confidence_score
        
        if score >= 0.8:
            return QualityCheck(
                check_name="confidence_score",
                result=ValidationResult.VALID,
                score=1.0,
                message="High confidence score",
                suggestions=[]
            )
        elif score >= self.min_confidence_threshold:
            return QualityCheck(
                check_name="confidence_score",
                result=ValidationResult.WARNING,
                score=0.7,
                message=f"Moderate confidence score: {score}",
                suggestions=["Consider requesting more specific analysis", "Validate with domain expert"]
            )
        else:
            return QualityCheck(
                check_name="confidence_score",
                result=ValidationResult.INVALID,
                score=0.3,
                message=f"Low confidence score: {score}",
                suggestions=["Re-run analysis with different prompt", "Provide more context", "Use different model"]
            )
    
    def _validate_content_quality(self, result: AnalysisResult) -> QualityCheck:
        """Validate content quality (length, clarity, completeness)"""
        issues = []
        score = 1.0
        
        # Check description length and quality
        if not result.description or len(result.description.strip()) < self.min_description_length:
            issues.append("Description too short or empty")
            score -= 0.3
        
        # Check recommendation length and quality
        if not result.recommendation or len(result.recommendation.strip()) < self.min_recommendation_length:
            issues.append("Recommendation too short or empty")
            score -= 0.3
        
        # Check for vague language
        vague_words = ["maybe", "possibly", "might", "could be", "perhaps", "potentially"]
        description_lower = result.description.lower()
        recommendation_lower = result.recommendation.lower()
        
        vague_count = sum(1 for word in vague_words if word in description_lower or word in recommendation_lower)
        if vague_count > 2:
            issues.append("Too much vague language")
            score -= 0.2
        
        # Check for specific metrics or examples
        has_metrics = bool(re.search(r'\d+%|\d+x|reduce|increase|improve', result.recommendation.lower()))
        if not has_metrics:
            score -= 0.1
        
        score = max(0.0, score)
        
        if score >= 0.8:
            return QualityCheck(
                check_name="content_quality",
                result=ValidationResult.VALID,
                score=score,
                message="Good content quality",
                suggestions=[]
            )
        elif score >= 0.5:
            return QualityCheck(
                check_name="content_quality",
                result=ValidationResult.WARNING,
                score=score,
                message="Content quality issues: " + ", ".join(issues),
                suggestions=["Add more specific details", "Include quantified benefits", "Reduce vague language"]
            )
        else:
            return QualityCheck(
                check_name="content_quality",
                result=ValidationResult.INVALID,
                score=score,
                message="Poor content quality: " + ", ".join(issues),
                suggestions=["Completely revise analysis", "Provide more context", "Use more specific prompts"]
            )
    
    def _validate_actionability(self, result: AnalysisResult) -> QualityCheck:
        """Validate actionability of recommendations"""
        score = 1.0
        issues = []
        
        # Check implementation steps
        if not result.implementation_steps or len(result.implementation_steps) < self.required_implementation_steps:
            issues.append("Missing or insufficient implementation steps")
            score -= 0.4
        
        # Check for action words in recommendation
        action_words = ["create", "add", "remove", "update", "modify", "implement", "configure", "set up", "change"]
        has_action_words = any(word in result.recommendation.lower() for word in action_words)
        if not has_action_words:
            issues.append("Recommendation lacks clear action words")
            score -= 0.3
        
        # Check effort estimation
        if result.effort not in self.effort_patterns:
            issues.append("Invalid effort estimation")
            score -= 0.2
        
        # Check for specific tools or methods mentioned
        specific_terms = ["field", "table", "view", "formula", "relationship", "validation", "automation"]
        has_specific_terms = any(term in result.recommendation.lower() for term in specific_terms)
        if not has_specific_terms:
            score -= 0.1
        
        score = max(0.0, score)
        
        if score >= 0.8:
            return QualityCheck(
                check_name="actionability",
                result=ValidationResult.VALID,
                score=score,
                message="Highly actionable recommendation",
                suggestions=[]
            )
        elif score >= 0.5:
            return QualityCheck(
                check_name="actionability",
                result=ValidationResult.WARNING,
                score=score,
                message="Actionability issues: " + ", ".join(issues),
                suggestions=["Add specific implementation steps", "Include clear action items", "Specify tools or methods"]
            )
        else:
            return QualityCheck(
                check_name="actionability",
                result=ValidationResult.INVALID,
                score=score,
                message="Poor actionability: " + ", ".join(issues),
                suggestions=["Rewrite with specific actions", "Add detailed implementation plan", "Focus on concrete steps"]
            )
    
    def _validate_specificity(self, result: AnalysisResult) -> QualityCheck:
        """Validate specificity of analysis"""
        score = 1.0
        issues = []
        
        # Check for specific table/field references
        has_table_refs = bool(re.search(r'table|field|column|record', result.description.lower()))
        if not has_table_refs:
            issues.append("Lacks specific table/field references")
            score -= 0.3
        
        # Check for generic vs specific language
        generic_phrases = ["improve performance", "better organization", "optimize structure", "enhance quality"]
        generic_count = sum(1 for phrase in generic_phrases if phrase in result.recommendation.lower())
        if generic_count > 1:
            issues.append("Too many generic phrases")
            score -= 0.2
        
        # Check for quantified benefits
        has_quantification = bool(re.search(r'\d+%|\d+x|by \d+|reduce.*\d+|increase.*\d+', result.estimated_improvement))
        if not has_quantification and result.estimated_improvement:
            score -= 0.2
        
        # Check category alignment specificity
        category_keywords = {
            AnalysisCategory.STRUCTURE: ["field", "organization", "layout", "grouping"],
            AnalysisCategory.NORMALIZATION: ["normalize", "relationship", "redundancy", "dependency"],
            AnalysisCategory.FIELD_TYPES: ["type", "format", "validation", "constraint"],
            AnalysisCategory.RELATIONSHIPS: ["link", "lookup", "rollup", "reference"],
            AnalysisCategory.PERFORMANCE: ["speed", "load", "query", "index"],
            AnalysisCategory.DATA_QUALITY: ["validation", "consistency", "accuracy", "completeness"]
        }
        
        relevant_keywords = category_keywords.get(result.category, [])
        has_category_keywords = any(keyword in result.description.lower() for keyword in relevant_keywords)
        if not has_category_keywords:
            score -= 0.2
        
        score = max(0.0, score)
        
        if score >= 0.8:
            return QualityCheck(
                check_name="specificity",
                result=ValidationResult.VALID,
                score=score,
                message="Highly specific analysis",
                suggestions=[]
            )
        elif score >= 0.5:
            return QualityCheck(
                check_name="specificity",
                result=ValidationResult.WARNING,
                score=score,
                message="Specificity issues: " + ", ".join(issues),
                suggestions=["Add specific table/field names", "Include quantified benefits", "Use category-specific terminology"]
            )
        else:
            return QualityCheck(
                check_name="specificity",
                result=ValidationResult.INVALID,
                score=score,
                message="Poor specificity: " + ", ".join(issues),
                suggestions=["Complete rewrite with specific details", "Focus on concrete elements", "Avoid generic language"]
            )
    
    def _validate_consistency(self, result: AnalysisResult) -> QualityCheck:
        """Validate internal consistency of analysis"""
        score = 1.0
        issues = []
        
        # Check priority vs effort consistency
        if result.priority == "high" and result.effort == "high":
            # High priority, high effort - should have strong justification
            if "critical" not in result.impact.lower() and "significant" not in result.impact.lower():
                issues.append("High priority/effort needs stronger impact justification")
                score -= 0.2
        
        # Check priority vs confidence consistency
        if result.priority == "high" and result.confidence_score < 0.7:
            issues.append("High priority recommendation should have higher confidence")
            score -= 0.2
        
        # Check effort vs implementation steps consistency
        step_count = len(result.implementation_steps)
        if result.effort == "low" and step_count > 3:
            issues.append("Low effort claim inconsistent with many implementation steps")
            score -= 0.2
        elif result.effort == "high" and step_count < 2:
            issues.append("High effort claim inconsistent with few implementation steps")
            score -= 0.2
        
        # Check category vs content alignment
        category_specific_checks = {
            AnalysisCategory.PERFORMANCE: ["performance", "speed", "optimization", "efficiency"],
            AnalysisCategory.DATA_QUALITY: ["quality", "validation", "consistency", "accuracy"],
            AnalysisCategory.RELATIONSHIPS: ["relationship", "link", "reference", "connection"]
        }
        
        if result.category in category_specific_checks:
            required_terms = category_specific_checks[result.category]
            content = (result.description + " " + result.recommendation).lower()
            if not any(term in content for term in required_terms):
                issues.append(f"Content doesn't align with {result.category.value} category")
                score -= 0.3
        
        score = max(0.0, score)
        
        if score >= 0.8:
            return QualityCheck(
                check_name="consistency",
                result=ValidationResult.VALID,
                score=score,
                message="Internally consistent analysis",
                suggestions=[]
            )
        elif score >= 0.5:
            return QualityCheck(
                check_name="consistency",
                result=ValidationResult.WARNING,
                score=score,
                message="Consistency issues: " + ", ".join(issues),
                suggestions=["Align priority with confidence", "Match effort with implementation complexity", "Ensure category alignment"]
            )
        else:
            return QualityCheck(
                check_name="consistency",
                result=ValidationResult.INVALID,
                score=score,
                message="Poor consistency: " + ", ".join(issues),
                suggestions=["Review all fields for alignment", "Revise priority/effort balance", "Ensure category-content match"]
            )
    
    def _validate_category_alignment(self, result: AnalysisResult) -> QualityCheck:
        """Validate alignment with analysis category"""
        # This is a more detailed version of category alignment
        category_validators = {
            AnalysisCategory.STRUCTURE: self._validate_structure_category,
            AnalysisCategory.NORMALIZATION: self._validate_normalization_category,
            AnalysisCategory.FIELD_TYPES: self._validate_field_types_category,
            AnalysisCategory.RELATIONSHIPS: self._validate_relationships_category,
            AnalysisCategory.PERFORMANCE: self._validate_performance_category,
            AnalysisCategory.DATA_QUALITY: self._validate_data_quality_category,
        }
        
        validator = category_validators.get(result.category)
        if validator:
            return validator(result)
        else:
            return QualityCheck(
                check_name="category_alignment",
                result=ValidationResult.WARNING,
                score=0.7,
                message=f"No specific validator for category {result.category.value}",
                suggestions=["Manually review category alignment"]
            )
    
    def _validate_structure_category(self, result: AnalysisResult) -> QualityCheck:
        """Validate structure analysis"""
        content = (result.description + " " + result.recommendation).lower()
        structure_terms = ["field", "organization", "layout", "grouping", "structure", "design", "schema"]
        
        if any(term in content for term in structure_terms):
            return QualityCheck(
                check_name="category_alignment",
                result=ValidationResult.VALID,
                score=1.0,
                message="Well-aligned with structure category",
                suggestions=[]
            )
        else:
            return QualityCheck(
                check_name="category_alignment",
                result=ValidationResult.WARNING,
                score=0.5,
                message="Weak alignment with structure category",
                suggestions=["Focus on table structure elements", "Mention field organization", "Address schema design"]
            )
    
    def _validate_normalization_category(self, result: AnalysisResult) -> QualityCheck:
        """Validate normalization analysis"""
        content = (result.description + " " + result.recommendation).lower()
        normalization_terms = ["normalize", "redundancy", "dependency", "relationship", "split", "separate", "duplicate"]
        
        if any(term in content for term in normalization_terms):
            return QualityCheck(
                check_name="category_alignment",
                result=ValidationResult.VALID,
                score=1.0,
                message="Well-aligned with normalization category",
                suggestions=[]
            )
        else:
            return QualityCheck(
                check_name="category_alignment",
                result=ValidationResult.WARNING,
                score=0.5,
                message="Weak alignment with normalization category",
                suggestions=["Address data redundancy", "Mention normalization principles", "Suggest table splitting"]
            )
    
    def _validate_field_types_category(self, result: AnalysisResult) -> QualityCheck:
        """Validate field types analysis"""
        content = (result.description + " " + result.recommendation).lower()
        field_terms = ["field type", "validation", "format", "constraint", "data type", "single line", "long text", "number", "date"]
        
        if any(term in content for term in field_terms):
            return QualityCheck(
                check_name="category_alignment",
                result=ValidationResult.VALID,
                score=1.0,
                message="Well-aligned with field types category",
                suggestions=[]
            )
        else:
            return QualityCheck(
                check_name="category_alignment",
                result=ValidationResult.WARNING,
                score=0.5,
                message="Weak alignment with field types category",
                suggestions=["Focus on field type optimization", "Address validation rules", "Mention data formats"]
            )
    
    def _validate_relationships_category(self, result: AnalysisResult) -> QualityCheck:
        """Validate relationships analysis"""
        content = (result.description + " " + result.recommendation).lower()
        relationship_terms = ["relationship", "link", "lookup", "rollup", "reference", "connection", "foreign key"]
        
        if any(term in content for term in relationship_terms):
            return QualityCheck(
                check_name="category_alignment",
                result=ValidationResult.VALID,
                score=1.0,
                message="Well-aligned with relationships category",
                suggestions=[]
            )
        else:
            return QualityCheck(
                check_name="category_alignment",
                result=ValidationResult.WARNING,
                score=0.5,
                message="Weak alignment with relationships category",
                suggestions=["Focus on table relationships", "Mention link fields", "Address lookup optimizations"]
            )
    
    def _validate_performance_category(self, result: AnalysisResult) -> QualityCheck:
        """Validate performance analysis"""
        content = (result.description + " " + result.recommendation).lower()
        performance_terms = ["performance", "speed", "optimization", "efficiency", "load time", "query", "index", "slow"]
        
        if any(term in content for term in performance_terms):
            return QualityCheck(
                check_name="category_alignment",
                result=ValidationResult.VALID,
                score=1.0,
                message="Well-aligned with performance category",
                suggestions=[]
            )
        else:
            return QualityCheck(
                check_name="category_alignment",
                result=ValidationResult.WARNING,
                score=0.5,
                message="Weak alignment with performance category",
                suggestions=["Focus on performance improvements", "Mention speed optimizations", "Address efficiency gains"]
            )
    
    def _validate_data_quality_category(self, result: AnalysisResult) -> QualityCheck:
        """Validate data quality analysis"""
        content = (result.description + " " + result.recommendation).lower()
        quality_terms = ["quality", "validation", "consistency", "accuracy", "completeness", "integrity", "clean", "standardize"]
        
        if any(term in content for term in quality_terms):
            return QualityCheck(
                check_name="category_alignment",
                result=ValidationResult.VALID,
                score=1.0,
                message="Well-aligned with data quality category",
                suggestions=[]
            )
        else:
            return QualityCheck(
                check_name="category_alignment",
                result=ValidationResult.WARNING,
                score=0.5,
                message="Weak alignment with data quality category",
                suggestions=["Focus on data quality issues", "Mention validation improvements", "Address consistency problems"]
            )
    
    def _calculate_result_quality_score(self, quality_checks: List[QualityCheck]) -> float:
        """Calculate overall quality score for a result"""
        if not quality_checks:
            return 0.0
        
        weighted_score = 0.0
        total_weight = 0.0
        
        for check in quality_checks:
            weight = self.quality_weights.get(check.check_name, 0.1)
            weighted_score += check.score * weight
            total_weight += weight
        
        return weighted_score / total_weight if total_weight > 0 else 0.0
    
    def _generate_quality_recommendations(self, validation_summary: Dict[str, Any]) -> List[str]:
        """Generate recommendations for improving analysis quality"""
        recommendations = []
        
        overall_score = validation_summary["overall_quality_score"]
        stats = validation_summary["statistics"]
        
        if overall_score < 0.6:
            recommendations.append("Overall analysis quality is below acceptable threshold. Consider refining prompts.")
        
        if stats["invalid_analyses"] > stats["total_analyses"] * 0.1:
            recommendations.append("High number of invalid analyses. Review prompt engineering and model parameters.")
        
        if stats["warning_analyses"] > stats["total_analyses"] * 0.3:
            recommendations.append("Many analyses have quality warnings. Consider post-processing improvements.")
        
        # Category-specific recommendations
        category_scores = validation_summary["category_scores"]
        for category, score in category_scores.items():
            if score < 0.5:
                recommendations.append(f"Poor quality in {category} analysis. Review category-specific prompts.")
        
        return recommendations