"""
Feature matching for image alignment
"""

import cv2
import numpy as np
from typing import Optional, List, Tuple, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

from ..core.models import Frame, ProcessingConfig
from ..core.utils import get_logger

logger = get_logger("processing.feature_matcher")


class MatcherType(Enum):
    """Feature matcher types"""
    FLANN = "flann"
    BFMATCHER = "bfmatcher"


class DetectorType(Enum):
    """Feature detector types"""
    SIFT = "sift"
    SURF = "surf"
    ORB = "orb"
    AKAZE = "akaze"


@dataclass
class MatchResult:
    """Result of feature matching"""
    matches: List[cv2.DMatch]  # List of matches
    good_matches: List[cv2.DMatch]  # Filtered good matches
    homography: Optional[np.ndarray] = None  # Estimated homography matrix
    confidence: float = 0.0  # Matching confidence (0-1)
    inliers: int = 0  # Number of inlier matches
    reprojection_error: float = 0.0  # Reprojection error
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "match_count": len(self.matches),
            "good_match_count": len(self.good_matches),
            "confidence": self.confidence,
            "inliers": self.inliers,
            "reprojection_error": self.reprojection_error,
        }


class FeatureMatcher:
    """Base class for feature matching"""
    
    def __init__(self, config: Optional[ProcessingConfig] = None):
        self.config = config or ProcessingConfig()
        self._detector: Optional[Any] = None
        self._matcher: Optional[Any] = None
        self._initialize()
    
    def _initialize(self) -> None:
        """Initialize detector and matcher"""
        pass
    
    def detect_and_compute(self, image: np.ndarray) -> Tuple[List[cv2.KeyPoint], np.ndarray]:
        """
        Detect keypoints and compute descriptors
        
        Args:
            image: Input image (grayscale)
        
        Returns:
            Tuple of (keypoints, descriptors)
        """
        raise NotImplementedError
    
    def match(self, desc1: np.ndarray, desc2: np.ndarray) -> List[cv2.DMatch]:
        """
        Match descriptors
        
        Args:
            desc1: Descriptors from first image
            desc2: Descriptors from second image
        
        Returns:
            List of matches
        """
        raise NotImplementedError
    
    def filter_matches(self, matches: List[cv2.DMatch]) -> List[cv2.DMatch]:
        """
        Filter matches based on ratio test
        
        Args:
            matches: Raw matches
        
        Returns:
            Filtered good matches
        """
        # Sort matches by distance
        matches.sort(key=lambda x: x.distance)
        
        # Apply ratio test (Lowe's ratio test)
        good_matches = []
        for i in range(1, len(matches)):
            if matches[i].distance < self.config.ratio_test * matches[i-1].distance:
                good_matches.append(matches[i])
        
        # Ensure minimum matches
        if len(good_matches) < self.config.min_matches:
            return []
        
        return good_matches
    
    def estimate_homography(
        self, 
        kp1: List[cv2.KeyPoint], 
        kp2: List[cv2.KeyPoint],
        matches: List[cv2.DMatch],
        confidence_threshold: float = 0.8
    ) -> Tuple[Optional[np.ndarray], List[cv2.DMatch], float]:
        """
        Estimate homography matrix from matches
        
        Args:
            kp1: Keypoints from first image
            kp2: Keypoints from second image
            matches: List of matches
            confidence_threshold: Minimum confidence for valid homography
        
        Returns:
            Tuple of (homography_matrix, inlier_matches, confidence)
        """
        if len(matches) < 4:
            return None, [], 0.0
        
        # Extract matched points
        src_pts = np.float32([kp1[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
        dst_pts = np.float32([kp2[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)
        
        # Find homography using RANSAC
        H, mask = cv2.findHomography(
            src_pts, dst_pts, 
            cv2.RANSAC, 
            self.config.reprojection_error
        )
        
        if H is None:
            return None, [], 0.0
        
        # Count inliers
        inlier_mask = mask.ravel().astype(bool)
        inlier_matches = [m for m, mask_val in zip(matches, inlier_mask) if mask_val]
        inlier_count = len(inlier_matches)
        
        # Calculate confidence
        confidence = inlier_count / len(matches) if matches else 0.0
        
        if confidence < confidence_threshold:
            return None, [], confidence
        
        return H, inlier_matches, confidence
    
    def match_frames(self, frame1: Frame, frame2: Frame) -> Optional[MatchResult]:
        """
        Match two frames and estimate transformation
        
        Args:
            frame1: First frame (reference)
            frame2: Second frame (current)
        
        Returns:
            MatchResult or None if matching failed
        """
        if frame1.data is None or frame2.data is None:
            logger.warning("Cannot match frames with no data")
            return None
        
        try:
            # Convert to grayscale
            gray1 = cv2.cvtColor(frame1.data, cv2.COLOR_BGR2GRAY)
            gray2 = cv2.cvtColor(frame2.data, cv2.COLOR_BGR2GRAY)
            
            # Detect and compute features
            kp1, desc1 = self.detect_and_compute(gray1)
            kp2, desc2 = self.detect_and_compute(gray2)
            
            if desc1 is None or desc2 is None:
                return None
            
            # Match descriptors
            matches = self.match(desc1, desc2)
            
            # Filter matches
            good_matches = self.filter_matches(matches)
            
            if len(good_matches) < self.config.min_matches:
                logger.debug(f"Not enough good matches: {len(good_matches)} < {self.config.min_matches}")
                return None
            
            # Estimate homography
            H, inlier_matches, confidence = self.estimate_homography(
                kp1, kp2, good_matches, self.config.confidence_threshold
            )
            
            if H is None:
                logger.debug("Failed to estimate homography")
                return None
            
            # Calculate reprojection error
            src_pts = np.float32([kp1[m.queryIdx].pt for m in inlier_matches]).reshape(-1, 1, 2)
            dst_pts = np.float32([kp2[m.trainIdx].pt for m in inlier_matches]).reshape(-1, 1, 2)
            
            # Transform source points using homography
            transformed_pts = cv2.perspectiveTransform(src_pts, H)
            
            # Calculate mean error
            errors = np.linalg.norm(transformed_pts - dst_pts, axis=2)
            reprojection_error = float(np.mean(errors))
            
            return MatchResult(
                matches=matches,
                good_matches=good_matches,
                homography=H,
                confidence=confidence,
                inliers=len(inlier_matches),
                reprojection_error=reprojection_error
            )
            
        except Exception as e:
            logger.error(f"Error matching frames: {e}")
            return None


class SIFTMatcher(FeatureMatcher):
    """SIFT feature matcher"""
    
    def _initialize(self) -> None:
        """Initialize SIFT detector"""
        try:
            self._detector = cv2.SIFT_create(nfeatures=self.config.min_features)
            
            # Initialize FLANN matcher
            FLANN_INDEX_KDTREE = 1
            index_params = dict(algorithm=FLANN_INDEX_KDTREE, trees=5)
            search_params = dict(checks=50)
            self._matcher = cv2.FlannBasedMatcher(index_params, search_params)
            
        except Exception as e:
            logger.error(f"Error initializing SIFT matcher: {e}")
            self._detector = None
            self._matcher = None
    
    def detect_and_compute(self, image: np.ndarray) -> Tuple[List[cv2.KeyPoint], np.ndarray]:
        """Detect and compute SIFT features"""
        if self._detector is None:
            return [], np.array([])
        
        try:
            kp, desc = self._detector.detectAndCompute(image, None)
            return kp, desc
        except Exception as e:
            logger.error(f"Error detecting SIFT features: {e}")
            return [], np.array([])
    
    def match(self, desc1: np.ndarray, desc2: np.ndarray) -> List[cv2.DMatch]:
        """Match SIFT descriptors using FLANN"""
        if self._matcher is None:
            # Fallback to BFMatcher
            bf = cv2.BFMatcher()
            return bf.knnMatch(desc1, desc2, k=2)
        
        try:
            matches = self._matcher.knnMatch(desc1, desc2, k=2)
            # Apply ratio test
            good_matches = []
            for m, n in matches:
                if m.distance < self.config.ratio_test * n.distance:
                    good_matches.append(m)
            return good_matches
        except Exception as e:
            logger.error(f"Error matching SIFT descriptors: {e}")
            return []


class ORBMatcher(FeatureMatcher):
    """ORB feature matcher"""
    
    def _initialize(self) -> None:
        """Initialize ORB detector"""
        try:
            self._detector = cv2.ORB_create(nfeatures=self.config.min_features)
            
            # Initialize BFMatcher for ORB (binary descriptors)
            self._matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
            
        except Exception as e:
            logger.error(f"Error initializing ORB matcher: {e}")
            self._detector = None
            self._matcher = None
    
    def detect_and_compute(self, image: np.ndarray) -> Tuple[List[cv2.KeyPoint], np.ndarray]:
        """Detect and compute ORB features"""
        if self._detector is None:
            return [], np.array([])
        
        try:
            kp, desc = self._detector.detectAndCompute(image, None)
            return kp, desc
        except Exception as e:
            logger.error(f"Error detecting ORB features: {e}")
            return [], np.array([])
    
    def match(self, desc1: np.ndarray, desc2: np.ndarray) -> List[cv2.DMatch]:
        """Match ORB descriptors using BFMatcher"""
        if self._matcher is None:
            return []
        
        try:
            matches = self._matcher.match(desc1, desc2)
            # Sort by distance
            matches.sort(key=lambda x: x.distance)
            return matches
        except Exception as e:
            logger.error(f"Error matching ORB descriptors: {e}")
            return []


class AKAZEMatcher(FeatureMatcher):
    """AKAZE feature matcher"""
    
    def _initialize(self) -> None:
        """Initialize AKAZE detector"""
        try:
            self._detector = cv2.AKAZE_create()
            
            # Initialize BFMatcher for AKAZE (binary descriptors)
            self._matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
            
        except Exception as e:
            logger.error(f"Error initializing AKAZE matcher: {e}")
            self._detector = None
            self._matcher = None
    
    def detect_and_compute(self, image: np.ndarray) -> Tuple[List[cv2.KeyPoint], np.ndarray]:
        """Detect and compute AKAZE features"""
        if self._detector is None:
            return [], np.array([])
        
        try:
            kp, desc = self._detector.detectAndCompute(image, None)
            return kp, desc
        except Exception as e:
            logger.error(f"Error detecting AKAZE features: {e}")
            return [], np.array([])
    
    def match(self, desc1: np.ndarray, desc2: np.ndarray) -> List[cv2.DMatch]:
        """Match AKAZE descriptors using BFMatcher"""
        if self._matcher is None:
            return []
        
        try:
            matches = self._matcher.match(desc1, desc2)
            # Sort by distance
            matches.sort(key=lambda x: x.distance)
            return matches
        except Exception as e:
            logger.error(f"Error matching AKAZE descriptors: {e}")
            return []


def create_matcher(matcher_type: str, config: Optional[ProcessingConfig] = None) -> FeatureMatcher:
    """Factory function to create a feature matcher"""
    matcher_type = matcher_type.lower()
    
    if matcher_type == "sift" or matcher_type == "flann":
        return SIFTMatcher(config)
    elif matcher_type == "orb":
        return ORBMatcher(config)
    elif matcher_type == "akaze":
        return AKAZEMatcher(config)
    else:
        logger.warning(f"Unknown matcher type: {matcher_type}, using SIFT")
        return SIFTMatcher(config)
