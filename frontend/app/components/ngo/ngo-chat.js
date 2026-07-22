// NGO Chat Functions - Add to NgoController scope
angular.module("foodBridgeApp").run(["$rootScope", "$timeout", "ChatService", "AuthService", function($rootScope, $timeout, ChatService, AuthService) {
    
    function scrollChatToBottom() {
        setTimeout(function() {
            var container = document.getElementById("chatMessagesContainer");
            if (container) {
                container.scrollTop = container.scrollHeight;
            }
        }, 100);
    }

    // Fetch participants for a donation
    $rootScope.fetchChatParticipants = function(donation) {
        return ChatService.getParticipants(donation.id).then(function(res) {
            console.log("[NGO] Participants:", res.data);
            donation.participants = res.data.participants || [];
            return donation.participants;
        }).catch(function(err) {
            console.error("[NGO] Failed to load participants:", err);
            return [];
        });
    };

    // Open chat with specific participant
    $rootScope.openChat = function(donation, targetRole) {
        console.log("[NGO] Opening chat for donation:", donation, "with target role:", targetRole);
        
        var donationId = donation.id || donation;
        console.log("[NGO] Using donation ID:", donationId);
        
        $rootScope.chatPanelOpen = true;
        $rootScope.currentDonationId = donationId;
        $rootScope.chatMessageText = "";
        $rootScope.chatLoading = true;
        $rootScope.selectedReceiverName = "";

        var token = AuthService.getToken();
        ChatService.connect(donationId, token);

        ChatService.getParticipants(donationId).then(function(res) {
            $rootScope.chatParticipants = res.data.participants || [];
            console.log("[NGO] Participants fetched:", $rootScope.chatParticipants);
            
            // Find the target participant based on role (case-insensitive)
            if (targetRole) {
                var target = $rootScope.chatParticipants.find(function(p) { 
                    return p.role && p.role.toLowerCase() === targetRole.toLowerCase(); 
                });
                if (target) {
                    $rootScope.chatSelectedReceiver = target.user_id;
                    $rootScope.selectedReceiverName = target.name;
                    console.log("[NGO] Selected receiver:", target.user_id, target.name);
                }
            } else {
                // Default: select first available participant (not current user)
                var others = $rootScope.chatParticipants.filter(function(p) {
                    return p.user_id !== $rootScope.currentUserId;
                });
                if (others.length > 0) {
                    $rootScope.chatSelectedReceiver = others[0].user_id;
                    $rootScope.selectedReceiverName = others[0].name;
                }
            }
        }).catch(function(err) {
            console.error("[NGO] Failed to load participants:", err);
        });

        ChatService.getMessages(donationId).then(function(res) {
            $rootScope.chatMessages = res.data || [];
            $rootScope.chatLoading = false;
            scrollChatToBottom();
        }).catch(function(err) {
            console.error("[NGO] Failed to load messages:", err);
            $rootScope.chatLoading = false;
        });
    };
    
    // Close chat
    $rootScope.closeChat = function() {
        console.log("[NGO] Closing chat panel");
        $rootScope.chatPanelOpen = false;
        if ($rootScope.currentDonationId) {
            ChatService.disconnect();
        }
    };
    
    // Send chat message
    $rootScope.sendChatMessage = function() {
        if (!$rootScope.chatMessageText || !$rootScope.chatSelectedReceiver || !$rootScope.currentDonationId) {
            return;
        }
        
        ChatService.sendMessage($rootScope.chatSelectedReceiver, $rootScope.currentDonationId, $rootScope.chatMessageText)
            .then(function(res) {
                $rootScope.chatMessageText = "";
                if (res.data && res.data.data) {
                    var msgs = res.data.data;
                    if (msgs.id) {
                        $rootScope.chatMessages.push(msgs);
                    }
                }
                scrollChatToBottom();
            }).catch(function(err) {
                console.error("[NGO] Send message error:", err);
            });
    };
    
    // Send on Enter key
    $rootScope.chatSendOnEnter = function(event) {
        if (event.key === 'Enter') {
            $rootScope.sendChatMessage();
        }
    };
}]);
