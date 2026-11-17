from math import asin, cos, radians, sin, sqrt


def _matching_faq(message: str, faqs: list[dict]) -> dict | None:
    question = message.casefold()
    matches = []
    for faq in faqs:
        keywords = [
            keyword.strip().casefold()
            for keyword in str(faq.get("keywords", "")).split("|")
            if keyword.strip()
        ]
        matched = [keyword for keyword in keywords if keyword in question]
        if matched:
            matches.append((max(map(len, matched)), faq))
    return max(matches, key=lambda match: match[0])[1] if matches else None


def _matching_hotlines(message: str, hotlines: list[dict]) -> list[dict]:
    question = message.casefold()
    matches = []
    for hotline in hotlines:
        keywords = [
            keyword.strip().casefold()
            for keyword in str(hotline.get("keywords", "")).split("|")
            if keyword.strip()
        ]
        if any(keyword in question for keyword in keywords):
            matches.append(hotline)
    return matches


def nearby_stations(latitude: float, longitude: float, stations: list[dict]) -> list[dict]:
    def distance_km(station: dict) -> float:
        lat1, lat2 = radians(latitude), radians(float(station["latitude"]))
        delta_lat = lat2 - lat1
        delta_lon = radians(float(station["longitude"]) - longitude)
        value = sin(delta_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(delta_lon / 2) ** 2
        return 6371 * 2 * asin(sqrt(value))

    results = []
    for station in stations:
        result = dict(station)
        result["distance_km"] = round(distance_km(station), 2)
        results.append(result)
    return sorted(results, key=lambda station: station["distance_km"])[:5]


def answer(
    message: str,
    role: str,
    stations: list[dict] | None = None,
    faqs: list[dict] | None = None,
    hotlines: list[dict] | None = None,
    police_contacts: list[dict] | None = None,
) -> str:
    question = message.casefold()
    if any(term in question for term in ("999", "emergency", "জরুরি", "বিপদ", "ambulance")):
        return (
            "এটি যদি তাৎক্ষণিক বিপদ বা জরুরি অবস্থা হয়, এখনই বাংলাদেশের জাতীয় "
            "জরুরি সেবা ৯৯৯-এ কল করুন। নিরাপদ স্থানে যান এবং এই চ্যাটের উত্তরের "
            "জন্য অপেক্ষা করবেন না।"
        )

    if any(term in question for term in ("nearby", "near", "নিকটস্থ", "কাছের", "কাছাকাছি")):
        if stations:
            lines = [
                f"• {station['name']} — {station['address']} "
                f"({station['distance_km']} km)"
                for station in stations
            ]
            return "আপনার দেওয়া অবস্থানের নিকটবর্তী যাচাইকৃত থানা:\n" + "\n".join(lines)
        return (
            "এই মুহূর্তে ডেটাবেসে যাচাইকৃত থানার অবস্থান পাওয়া যায়নি। অবস্থান "
            "শেয়ার করতে চাইলে Nearby police station বোতাম ব্যবহার করুন; জরুরি "
            "সহায়তার জন্য ৯৯৯-এ কল করুন।"
        )

    faq = _matching_faq(question, faqs or [])
    if faq:
        return str(faq["answer"])

    matching_hotlines = _matching_hotlines(question, hotlines or [])
    if matching_hotlines:
        details = []
        for hotline in matching_hotlines:
            details.append(
                f"{hotline['service_name']}: {hotline['phone_number']} "
                f"({'যাচাইকৃত' if hotline['verified'] else 'যাচাই বাকি'})"
            )
        response = "ডেটাবেসের জরুরি যোগাযোগ:\n" + "\n".join(details)
        if any(not hotline["verified"] for hotline in matching_hotlines):
            response += (
                "\nযাচাই বাকি নম্বরের ওপর জরুরি অবস্থায় নির্ভর করবেন না। "
                "তাৎক্ষণিক বিপদে ৯৯৯-এ কল করুন।"
            )
        return response

    if any(
        term in question
        for term in (
            "police station",
            "thana",
            "থানার নম্বর",
            "থানার ফোন",
            "oc number",
            "duty officer",
            "police phone",
            "station number",
        )
    ):
        if police_contacts:
            lines = []
            for contact in police_contacts:
                numbers = [
                    f"{label}: {contact[field]}"
                    for field, label in (
                        ("official_phone", "পুরোনো অফিস নম্বর"),
                        ("listed_phone", "তালিকাভুক্ত নম্বর"),
                        ("new_phone", "ডিরেক্টরিতে নতুন নম্বর"),
                    )
                    if contact.get(field)
                ]
                lines.append(
                    f"• {contact['station_name']} — "
                    + (", ".join(numbers) if numbers else "নম্বর তালিকাভুক্ত নেই")
                )
            return (
                "মিল পাওয়া যোগাযোগগুলো বাংলাদেশ পুলিশের ২০২০ সালের ডিরেক্টরি "
                "থেকে; বর্তমান নম্বর হিসেবে যাচাই করা হয়নি:\n"
                + "\n".join(lines)
                + "\nনম্বরটি আগে সরকারি উৎসে যাচাই করুন; জরুরি অবস্থায় ৯৯৯-এ কল করুন।"
            )
        return (
            "এই নামে যাচাইকৃত বর্তমান থানার যোগাযোগ পাওয়া যায়নি। পুলিশ "
            "ডিরেক্টরির পুরোনো নম্বরগুলো ২০২০ সালের এবং যাচাই করা নয়। জরুরি "
            "সহায়তার জন্য ৯৯৯-এ কল করুন।"
        )

    if any(term in question for term in ("report", "gd", "fir", "অভিযোগ", "রিপোর্ট", "জিডি")):
        return (
            "থানায় অভিযোগ জানাতে নিকটস্থ থানার ডিউটি অফিসার/ডেস্কে ঘটনাটি বলুন। "
            "সময়, তারিখ, স্থান, কী ঘটেছে এবং প্রাসঙ্গিক প্রমাণ গুছিয়ে রাখুন। "
            "জিডি বা FIR প্রযোজ্য কি না ও পরবর্তী ধাপ পুলিশকে জিজ্ঞেস করুন এবং "
            "জমা দেওয়া নথি/রেফারেন্সের তথ্য সংরক্ষণ করুন। আইনি জরুরি পরিস্থিতিতে "
            "৯৯৯-এ কল করুন; এই সহকারী আইনি পরামর্শ নয়।"
        )

    if role == "POLICE":
        return (
            "রিপোর্ট পর্যালোচনার সময় তথ্য যাচাই করুন, নিরপেক্ষ নোট লিখুন এবং "
            "যাচাই ছাড়া কোনো জরিমানা বা সিদ্ধান্ত দেবেন না। জরুরি ঝুঁকি থাকলে "
            "স্থানীয় জরুরি প্রোটোকল অনুসরণ করুন।"
        )
    if role == "DRIVER":
        return (
            "যাত্রী ও পথচারীর নিরাপত্তাকে অগ্রাধিকার দিন। জরুরি অবস্থা বা "
            "দুর্ঘটনায় নিরাপদ স্থানে থামুন এবং বাংলাদেশের জরুরি সেবা ৯৯৯-এ "
            "যোগাযোগ করুন।"
        )
    return (
        "আমি জরুরি যোগাযোগ, থানায় অভিযোগ জানানোর সাধারণ ধাপ, এবং যাচাইকৃত "
        "নিকটবর্তী থানার তথ্য দিতে পারি। আপনার প্রশ্নটি আরেকটু নির্দিষ্ট করে লিখুন।"
    )
