"""ORM tables. Importing this package registers every table on Base.metadata."""
from app.models.community import Campaign, Comment, Pledge, Reaction, VolunteerSignup, VolunteerTask
from app.models.crm import Bid, BidMessage, BidOffer, Notification, Organization, Tender, User
from app.models.geo import (AdminArea, AreaIndicator, DeclarationMention, DeclarationSource, DistrictIndicator,
                            DroughtDeclaration, GeocodeCache, SourceDomain)
from app.models.intel import (LongTermPlan, PipelineRun, ReliefBrief, Signal, SignalFeedback, SignalLabel,
                              SignalLocation, Zone, ZoneSignal, ZoneSnapshot)

__all__ = [
    "AdminArea", "AreaIndicator", "DeclarationMention", "DeclarationSource", "DistrictIndicator", "DroughtDeclaration",
    "GeocodeCache", "SourceDomain",
    "LongTermPlan", "PipelineRun", "ReliefBrief", "Signal", "SignalFeedback", "SignalLabel",
    "SignalLocation", "Zone", "ZoneSignal", "ZoneSnapshot",
    "Bid", "BidMessage", "BidOffer", "Notification", "Organization", "Tender", "User",
    "Campaign", "Comment", "Pledge", "Reaction", "VolunteerSignup", "VolunteerTask",
]
