require "open-uri"
require "json"
require "nokogiri"

module SwimChi
  Facility = Data.define(:title, :documents, :address)

  class FacilityParser
    def self.parse(document)
      (document / "article > .facility").map do |facility|
        Facility.new(
          title: (facility / ".facility--title").text.strip,
          documents: (facility / ".facility--documents a").map do |l|
            {href: l.attr("href"), text: l.text.strip}
          end,
          address: (facility / ".facility--address").text.strip
        )
      end
    end
  end

  class Fetcher
    URL = "https://www.chicagoparkdistrict.com/views/ajax?view_name=facilities&view_display_id=facility_by_type&view_args=2491&page=%d"

    def self.fetch
      page = 0
      doc = fetch_page(page)
      last_page = (doc / ".pager__item--last a").attr("href").value.match(/page=(\d+)/)[1].to_i

      facilities = FacilityParser.parse(doc)
      facilities += FacilityParser.parse(fetch_page(page += 1)) while page < last_page
      pp(facilities)
    end

    def self.fetch_page(page)
      p(page)
      Nokogiri(JSON.parse(URI(format(URL, page)).read).dig(3, "data"))
    end
  end
end

SwimChi::Fetcher.fetch
