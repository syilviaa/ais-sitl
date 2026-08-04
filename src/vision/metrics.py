"""Small, dependency-free helpers for mAP@0.5 evaluation."""

from dataclasses import dataclass

from .models import BoundingBox, VisionClass


@dataclass(frozen=True)
class GroundTruth:
    image_id: str
    class_name: VisionClass
    bbox: BoundingBox


@dataclass(frozen=True)
class Prediction:
    image_id: str
    class_name: VisionClass
    confidence: float
    bbox: BoundingBox

    def __post_init__(self):
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")


def iou(left, right):
    """Return intersection-over-union for two pixel bounding boxes."""
    intersection_width = max(
        0.0,
        min(left.x2, right.x2) - max(left.x1, right.x1),
    )
    intersection_height = max(
        0.0,
        min(left.y2, right.y2) - max(left.y1, right.y1),
    )
    intersection = intersection_width * intersection_height
    left_area = (left.x2 - left.x1) * (left.y2 - left.y1)
    right_area = (right.x2 - right.x1) * (right.y2 - right.y1)
    union = left_area + right_area - intersection
    return intersection / union if union else 0.0


def _average_precision(predictions, truths, iou_threshold):
    if not truths:
        return None

    truths_by_image = {}
    for truth in truths:
        truths_by_image.setdefault(truth.image_id, []).append(truth)
    matched = {
        image_id: [False] * len(items)
        for image_id, items in truths_by_image.items()
    }

    true_positives = []
    false_positives = []
    for prediction in sorted(
        predictions,
        key=lambda item: item.confidence,
        reverse=True,
    ):
        candidates = truths_by_image.get(prediction.image_id, [])
        best_index = None
        best_iou = 0.0
        for index, truth in enumerate(candidates):
            overlap = iou(prediction.bbox, truth.bbox)
            if not matched[prediction.image_id][index] and overlap > best_iou:
                best_iou = overlap
                best_index = index

        is_match = best_index is not None and best_iou >= iou_threshold
        if is_match:
            matched[prediction.image_id][best_index] = True
        true_positives.append(1 if is_match else 0)
        false_positives.append(0 if is_match else 1)

    if not predictions:
        return 0.0

    cumulative_true = 0
    cumulative_false = 0
    recalls = []
    precisions = []
    for true_positive, false_positive in zip(
        true_positives,
        false_positives,
    ):
        cumulative_true += true_positive
        cumulative_false += false_positive
        recalls.append(cumulative_true / len(truths))
        precisions.append(
            cumulative_true / (cumulative_true + cumulative_false)
        )

    for index in range(len(precisions) - 2, -1, -1):
        precisions[index] = max(precisions[index], precisions[index + 1])

    average_precision = 0.0
    previous_recall = 0.0
    for recall, precision in zip(recalls, precisions):
        if recall > previous_recall:
            average_precision += (recall - previous_recall) * precision
            previous_recall = recall
    return average_precision


def evaluate_map50(predictions, ground_truths):
    """Calculate AP@0.5 per MVP class and their arithmetic mean."""
    per_class = {}
    scored_classes = []
    for class_name in VisionClass:
        class_predictions = [
            item for item in predictions if item.class_name == class_name
        ]
        class_truths = [
            item for item in ground_truths if item.class_name == class_name
        ]
        ap50 = _average_precision(
            class_predictions,
            class_truths,
            iou_threshold=0.5,
        )
        per_class[class_name.value] = {
            "ground_truths": len(class_truths),
            "predictions": len(class_predictions),
            "ap50": ap50,
        }
        if ap50 is not None:
            scored_classes.append(ap50)

    return {
        "iou_threshold": 0.5,
        "per_class": per_class,
        "map50": (
            sum(scored_classes) / len(scored_classes)
            if scored_classes
            else None
        ),
    }
