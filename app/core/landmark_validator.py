
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass
import logging

@dataclass
class Landmark:

    role: str
    selector: str
    label: Optional[str]
    labelledby: Optional[str]
    tag: str
    id: Optional[str]
    classes: List[str]
    has_heading: bool
    nested_landmarks: List['Landmark'] = None

    def __post_init__(self):
        if self.nested_landmarks is None:
            self.nested_landmarks = []

class LandmarkValidator:



    REQUIRED_LANDMARKS = {
        "main": "Main content landmark",
        "banner": "Site banner/header",
        "contentinfo": "Footer information"
    }


    RECOMMENDED_LANDMARKS = {
        "navigation": "Navigation region",
        "search": "Search feature",
        "complementary": "Complementary content",
        "form": "Form region"
    }


    SHOULD_BE_UNIQUE = {
        "main", "banner", "contentinfo"
    }

    def __init__(self):
        self._logger = logging.getLogger(__name__)

    def validate(self, landmarks: List[Dict[str, Any]]) -> Dict[str, Any]:

        if not landmarks:
            return {
                "valid": False,
                "issues": [{
                    "type": "no_landmarks",
                    "severity": "serious",
                    "description": "Page has no landmark regions",
                    "wcag": "1.3.1"
                }],
                "landmarks": [],
                "statistics": self._get_statistics([])
            }


        landmark_objects = self._build_landmarks(landmarks)


        issues = []


        missing_issues = self._check_missing_landmarks(landmark_objects)
        issues.extend(missing_issues)


        duplicate_issues = self._check_duplicate_landmarks(landmark_objects)
        issues.extend(duplicate_issues)


        nested_issues = self._check_nested_landmarks(landmark_objects)
        issues.extend(nested_issues)


        labeling_issues = self._check_landmark_labeling(landmark_objects)
        issues.extend(labeling_issues)


        hierarchy_issues = self._check_hierarchy(landmark_objects)
        issues.extend(hierarchy_issues)


        structure = self._build_structure_tree(landmark_objects)

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "landmarks": [self._landmark_to_dict(l) for l in landmark_objects],
            "structure": structure,
            "statistics": self._get_statistics(landmark_objects)
        }

    def _build_landmarks(self, landmarks: List[Dict]) -> List[Landmark]:

        result = []
        for l in landmarks:
            landmark = Landmark(
                role=l.get("role", ""),
                selector=l.get("selector", ""),
                label=l.get("label"),
                labelledby=l.get("labelledby"),
                tag=l.get("tag", ""),
                id=l.get("id"),
                classes=l.get("classes", []),
                has_heading=l.get("hasHeading", False)
            )
            result.append(landmark)
        return result

    def _landmark_to_dict(self, landmark: Landmark) -> Dict:

        return {
            "role": landmark.role,
            "selector": landmark.selector,
            "label": landmark.label,
            "labelledby": landmark.labelledby,
            "tag": landmark.tag,
            "id": landmark.id,
            "classes": landmark.classes,
            "has_heading": landmark.has_heading,
            "nested_landmarks": [
                self._landmark_to_dict(n) for n in landmark.nested_landmarks
            ] if landmark.nested_landmarks else []
        }

    def _check_missing_landmarks(self, landmarks: List[Landmark]) -> List[Dict]:

        issues = []
        present_roles = {l.role for l in landmarks}


        for role, description in self.REQUIRED_LANDMARKS.items():
            if role not in present_roles:
                issues.append({
                    "type": "missing_landmark",
                    "severity": "serious" if role == "main" else "moderate",
                    "description": f"Missing {role} landmark: {description}",
                    "wcag": "1.3.1",
                    "landmark": {
                        "role": role,
                        "required": True
                    }
                })

        return issues

    def _check_duplicate_landmarks(self, landmarks: List[Landmark]) -> List[Dict]:

        issues = []
        role_counts: Dict[str, List[Landmark]] = {}


        for landmark in landmarks:
            if landmark.role not in role_counts:
                role_counts[landmark.role] = []
            role_counts[landmark.role].append(landmark)


        for role, instances in role_counts.items():
            if role in self.SHOULD_BE_UNIQUE and len(instances) > 1:

                unlabeled = [
                    i for i in instances
                    if not i.label and not i.labelledby
                ]

                if unlabeled:
                    issues.append({
                        "type": "duplicate_landmark",
                        "severity": "moderate",
                        "description": f"Multiple {role} landmarks without unique labels",
                        "count": len(unlabeled),
                        "wcag": "2.4.1",
                        "landmarks": [
                            {
                                "role": role,
                                "selector": l.selector,
                                "tag": l.tag
                            } for l in unlabeled
                        ]
                    })

        return issues

    def _check_nested_landmarks(self, landmarks: List[Landmark]) -> List[Dict]:

        issues = []


        for landmark in landmarks:

            if landmark.role == "main":
                for other in landmarks:
                    if other != landmark and other.role == "main":

                        if self._is_nested(landmark, other):
                            issues.append({
                                "type": "nested_main",
                                "severity": "serious",
                                "description": "Main landmark nested inside another main",
                                "wcag": "1.3.1",
                                "landmarks": [
                                    {"role": "main", "selector": landmark.selector},
                                    {"role": "main", "selector": other.selector}
                                ]
                            })


            if landmark.role == "banner" and self._is_in_main(landmark, landmarks):
                issues.append({
                    "type": "banner_in_main",
                    "severity": "moderate",
                    "description": "Banner landmark inside main content",
                    "wcag": "1.3.1",
                    "landmark": {
                        "role": "banner",
                        "selector": landmark.selector
                    }
                })


            if landmark.role == "contentinfo" and self._is_in_main(landmark, landmarks):
                issues.append({
                    "type": "contentinfo_in_main",
                    "severity": "moderate",
                    "description": "Contentinfo landmark inside main content",
                    "wcag": "1.3.1",
                    "landmark": {
                        "role": "contentinfo",
                        "selector": landmark.selector
                    }
                })

        return issues

    def _check_landmark_labeling(self, landmarks: List[Landmark]) -> List[Dict]:

        issues = []

        for landmark in landmarks:

            if landmark.role == "region" and not landmark.has_heading:
                issues.append({
                    "type": "region_no_heading",
                    "severity": "moderate",
                    "description": "Region landmark should have a heading",
                    "wcag": "2.4.10",
                    "landmark": {
                        "role": "region",
                        "selector": landmark.selector
                    }
                })


            if landmark.role == "navigation":
                nav_count = sum(1 for l in landmarks if l.role == "navigation")
                if nav_count > 1 and not landmark.label and not landmark.labelledby:
                    issues.append({
                        "type": "navigation_unlabeled",
                        "severity": "moderate",
                        "description": "Multiple navigation landmarks require unique labels",
                        "wcag": "2.4.1",
                        "landmark": {
                            "role": "navigation",
                            "selector": landmark.selector
                        }
                    })

        return issues

    def _check_hierarchy(self, landmarks: List[Landmark]) -> List[Dict]:

        issues = []


        for landmark in landmarks:

            parent = self._find_parent_landmark(landmark, landmarks)

            if parent:

                if parent.role == "banner" and landmark.role == "main":
                    issues.append({
                        "type": "main_under_banner",
                        "severity": "moderate",
                        "description": "Main landmark should not be under banner",
                        "wcag": "1.3.1",
                        "relationship": {
                            "parent": {"role": parent.role, "selector": parent.selector},
                            "child": {"role": landmark.role, "selector": landmark.selector}
                        }
                    })

        return issues

    def _is_nested(self, landmark1: Landmark, landmark2: Landmark) -> bool:


        selector1 = landmark1.selector
        selector2 = landmark2.selector

        if not selector1 or not selector2:
            return False



        return selector2 in selector1 or selector1.startswith(selector2 + " ")

    def _is_in_main(self, landmark: Landmark, all_landmarks: List[Landmark]) -> bool:

        main_landmarks = [l for l in all_landmarks if l.role == "main"]

        for main in main_landmarks:
            if self._is_nested(landmark, main):
                return True

        return False

    def _find_parent_landmark(
        self,
        landmark: Landmark,
        all_landmarks: List[Landmark]
    ) -> Optional[Landmark]:

        for potential_parent in all_landmarks:
            if potential_parent != landmark:
                if self._is_nested(landmark, potential_parent):
                    return potential_parent
        return None

    def _build_structure_tree(self, landmarks: List[Landmark]) -> List[Dict]:


        roots = []
        for landmark in landmarks:
            parent = self._find_parent_landmark(landmark, landmarks)
            if not parent:
                roots.append(landmark)


        def build_node(landmark: Landmark) -> Dict:
            node = {
                "role": landmark.role,
                "selector": landmark.selector,
                "label": landmark.label,
                "tag": landmark.tag,
                "children": []
            }


            for l in landmarks:
                if l != landmark and self._find_parent_landmark(l, landmarks) == landmark:
                    node["children"].append(build_node(l))

            return node

        return [build_node(root) for root in roots]

    def _get_statistics(self, landmarks: List[Landmark]) -> Dict[str, Any]:

        stats = {
            "total_landmarks": len(landmarks),
            "by_role": {},
            "labeled": 0,
            "unlabeled": 0,
            "with_headings": 0,
            "without_headings": 0
        }

        for l in landmarks:

            if l.role not in stats["by_role"]:
                stats["by_role"][l.role] = 0
            stats["by_role"][l.role] += 1


            if l.label or l.labelledby:
                stats["labeled"] += 1
            else:
                stats["unlabeled"] += 1


            if l.has_heading:
                stats["with_headings"] += 1
            else:
                stats["without_headings"] += 1

        return stats